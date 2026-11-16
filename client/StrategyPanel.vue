<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

const props = defineProps<{ symbol: string; fast: number; slow: number }>();
const emit = defineEmits<{ windows: [fast: number, slow: number] }>();
type Run = {
  id: string;
  mode: "paper" | "backtest";
  status: string;
  symbol: string;
  untilReceipt: number;
  processedReceipts: number;
  firstReceiptTime: number;
  lastReceiptTime: number;
  config: {
    fast: number;
    slow: number;
    initialCash: number;
    feeBps: number;
    slippageBps: number;
  };
  summary: {
    cash: number;
    quantity: string;
    costBasis: number;
    equity: number;
    realizedPnl: number;
    unrealizedPnl: number;
    returnPercent: number;
    maxDrawdownPercent: number;
    fees: number;
    completedBars: number;
    fills: number;
    signals: number;
    markPrice: string | null;
  };
  orders: {
    id: number;
    side: string;
    status: string;
    signalTime: number;
    decisionTime: number;
    signalReceiptId: number;
  }[];
  fills: {
    orderId: number;
    side: string;
    quantity: string;
    price: number;
    fee: number;
    realizedPnl: number;
    sourceTime: number;
    receivedAt: number;
    receiptId: number;
    quoteObservationId: number;
  }[];
  equity: { time: number; value: number }[];
};
type RunChoice = Pick<Run, "id" | "mode" | "status" | "symbol"> & {
  createdAt: number;
};
const experiment = ref<"backtest" | "paper">("backtest");
const fastInput = ref(props.fast),
  slowInput = ref(props.slow);
const cash = ref(10000),
  fee = ref(10),
  slippage = ref(5);
const run = ref<Run | null>(null),
  saved = ref<RunChoice[]>([]);
const busy = ref(false),
  error = ref(""),
  ledger = ref<"fills" | "orders">("fills");
let requestVersion = 0,
  detailVersion = 0,
  refresh: ReturnType<typeof setInterval> | undefined;
const money = (value: number) =>
  value.toLocaleString("en-US", { style: "currency", currency: "USD" });
const when = (value: number) =>
  new Date(value).toISOString().replace("T", " ").slice(0, 19) + " UTC";
const valid = computed(
  () =>
    Number.isInteger(fastInput.value) &&
    Number.isInteger(slowInput.value) &&
    fastInput.value >= 2 &&
    fastInput.value < slowInput.value &&
    slowInput.value <= 200,
);
const choices = computed(() =>
  saved.value.filter((r) => r.mode === experiment.value),
);
const shown = computed(() =>
  run.value?.mode === experiment.value ? run.value : null,
);
const curve = computed(() => {
  const points = shown.value?.equity ?? [];
  const initial = shown.value?.config.initialCash ?? 10000;
  const values = points.map((p) => p.value);
  const min = Math.min(initial, ...values),
    max = Math.max(initial, ...values);
  const span = Math.max(max - min, initial * 0.001);
  const firstTime = points[0]?.time ?? 0;
  const timeSpan = Math.max(1, (points.at(-1)?.time ?? 0) - firstTime);
  return {
    min,
    max,
    path: points
      .map(
        (p, i) =>
          `${i ? "L" : "M"}${25 + ((p.time - firstTime) / timeSpan) * 910},${115 - ((p.value - min) / span) * 90}`,
      )
      .join(" "),
  };
});
async function json(url: string, options?: RequestInit) {
  const response = await fetch(url, options);
  const value = await response.json();
  if (!response.ok)
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
        : (value.error ?? "Check the settings and try again."),
    );
  return value;
}
watch([fastInput, slowInput], () => {
  if (valid.value) emit("windows", fastInput.value, slowInput.value);
});
async function loadSaved() {
  const version = ++requestVersion;
  try {
    const value = await json(`/api/simulations?symbol=${props.symbol}`);
    if (version !== requestVersion) return;
    saved.value = value.runs;
    const latest = choices.value[0];
    if (latest) await loadRun(latest.id);
  } catch (e) {
    if (version === requestVersion) error.value = (e as Error).message;
  }
}
async function loadRun(id: string) {
  const version = requestVersion;
  const detail = ++detailVersion;
  const value = await json(`/api/simulations/${id}`);
  if (
    version === requestVersion &&
    detail === detailVersion &&
    value.symbol === props.symbol
  )
    run.value = value;
}
async function createRun() {
  busy.value = true;
  error.value = "";
  const version = requestVersion;
  try {
    const value = await json("/api/simulations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: props.symbol,
        mode: experiment.value,
        fast: fastInput.value,
        slow: slowInput.value,
        initialCash: cash.value,
        feeBps: fee.value,
        slippageBps: slippage.value,
      }),
    });
    if (version !== requestVersion) return;
    run.value = value;
    const list = await json(`/api/simulations?symbol=${props.symbol}`);
    if (version === requestVersion) saved.value = list.runs;
  } catch (e) {
    if (version === requestVersion) error.value = (e as Error).message;
  } finally {
    if (version === requestVersion) busy.value = false;
  }
}
async function pause() {
  if (!shown.value) return;
  busy.value = true;
  const version = requestVersion;
  try {
    const value = await json(`/api/simulations/${shown.value.id}/pause`, {
      method: "POST",
    });
    if (version === requestVersion) {
      run.value = value;
      saved.value = saved.value.map((r) =>
        r.id === value.id ? { ...r, status: value.status } : r,
      );
    }
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
watch(
  () => props.symbol,
  () => {
    run.value = null;
    saved.value = [];
    error.value = "";
    busy.value = false;
    loadSaved();
  },
  { immediate: true },
);
watch(experiment, () => {
  requestVersion++;
  detailVersion++;
  busy.value = false;
  error.value = "";
  const latest = choices.value[0];
  run.value = null;
  if (latest) loadRun(latest.id).catch((e) => (error.value = e.message));
});
watch(shown, (value) => {
  clearInterval(refresh);
  if (value?.status === "running")
    refresh = setInterval(() => {
      loadRun(value.id).catch((e) => (error.value = e.message));
    }, 3000);
});
onUnmounted(() => {
  requestVersion++;
  clearInterval(refresh);
});
</script>

<template>
  <section class="panel strategy-panel" aria-label="Strategy laboratory">
    <div class="strategy-heading">
      <div>
        <div class="eyebrow">PART 4.2 · SIMULATED TRADING</div>
        <h2>From crossover to outcome<span class="heading-dot">.</span></h2>
        <p>
          Follow the same SMA rules through recorded observations or a paper
          account.
        </p>
      </div>
      <span class="simulation-badge">SIMULATED · USD</span>
    </div>
    <div class="experiment-tabs" role="tablist" aria-label="Strategy mode">
      <button
        role="tab"
        :aria-selected="experiment === 'backtest'"
        @click="experiment = 'backtest'"
      >
        Historical backtest
      </button>
      <button
        role="tab"
        :aria-selected="experiment === 'paper'"
        @click="experiment = 'paper'"
      >
        Paper account
      </button>
    </div>
    <form class="strategy-form" @submit.prevent="createRun">
      <label
        >Fast SMA<input
          aria-label="Fast SMA"
          type="number"
          min="2"
          max="199"
          step="1"
          v-model.number="fastInput"
          required
      /></label>
      <label
        >Slow SMA<input
          aria-label="Slow SMA"
          type="number"
          min="3"
          max="200"
          step="1"
          v-model.number="slowInput"
          required
      /></label>
      <label
        >Starting cash<input
          aria-label="Starting cash"
          type="number"
          min="100"
          max="1000000"
          step="0.01"
          v-model.number="cash"
          required
      /></label>
      <label
        >Fee (bps / side)<input
          aria-label="Fee basis points"
          type="number"
          min="0"
          max="100"
          step="0.1"
          v-model.number="fee"
          required
      /></label>
      <label
        >Slippage (bps)<input
          aria-label="Slippage basis points"
          type="number"
          min="0"
          max="100"
          step="0.1"
          v-model.number="slippage"
          required
      /></label>
      <button type="submit" class="strategy-primary" :disabled="busy || !valid">
        {{
          busy
            ? "Processing receipts…"
            : experiment === "backtest"
              ? "Run backtest"
              : "Start paper account"
        }}
      </button>
    </form>
    <p v-if="!valid" class="strategy-error" role="alert">
      Choose whole lengths with 2 ≤ fast &lt; slow ≤ 200.
    </p>
    <p class="experiment-description">
      {{
        experiment === "backtest"
          ? "Frozen history · all saved receipts for " +
            symbol +
            " · each decision uses only observations already received."
          : "Future receipts · historical bars warm up the SMAs. A running account waits for a new completed-bar crossover."
      }}
    </p>
    <p v-if="error" role="alert" class="strategy-error">{{ error }}</p>
    <div class="saved-runs" v-if="choices.length">
      <label
        >Saved experiments
        <select
          aria-label="Saved experiments"
          :value="shown?.id ?? ''"
          @change="loadRun(($event.target as HTMLSelectElement).value)"
        >
          <option v-for="r in choices" :key="r.id" :value="r.id">
            {{ when(r.createdAt) }} · {{ r.status }} · {{ r.id.slice(0, 6) }}
          </option>
        </select></label
      >
      <button
        v-if="shown?.status === 'running'"
        class="strategy-secondary"
        :disabled="busy"
        @click="pause"
      >
        Pause paper account
      </button>
    </div>
    <template v-if="shown">
      <div class="run-context">
        <strong
          >{{
            shown.mode === "paper" ? "PAPER ACCOUNT" : "HISTORICAL BACKTEST"
          }}
          · {{ shown.status.toUpperCase() }}</strong
        >
        <span
          >{{ shown.symbol }} · SMA {{ shown.config.fast }} /
          {{ shown.config.slow }} · {{ shown.config.feeBps }} bps fee ·
          {{ shown.config.slippageBps }} bps slippage</span
        >
        <span
          >{{ when(shown.firstReceiptTime) }} →
          {{ when(shown.lastReceiptTime) }}</span
        >
      </div>
      <div class="account-metrics">
        <div>
          <span>Account equity</span
          ><strong>{{ money(shown.summary.equity) }}</strong
          ><small
            :class="shown.summary.returnPercent >= 0 ? 'positive' : 'negative'"
            >{{ shown.summary.returnPercent.toFixed(2) }}% return</small
          >
        </div>
        <div>
          <span>Cash available</span
          ><strong>{{ money(shown.summary.cash) }}</strong
          ><small>{{ money(shown.config.initialCash) }} starting balance</small>
        </div>
        <div>
          <span>Position · {{ symbol }}</span
          ><strong>{{ Number(shown.summary.quantity).toFixed(8) }}</strong
          ><small>{{ money(shown.summary.costBasis) }} cost basis</small>
        </div>
        <div>
          <span>Realized P&amp;L</span
          ><strong>{{ money(shown.summary.realizedPnl) }}</strong
          ><small>After fees on closed positions</small>
        </div>
        <div>
          <span>Unrealized P&amp;L</span
          ><strong>{{ money(shown.summary.unrealizedPnl) }}</strong
          ><small>Marked to last observed quote</small>
        </div>
        <div>
          <span>Maximum drawdown</span
          ><strong>{{ shown.summary.maxDrawdownPercent.toFixed(2) }}%</strong
          ><small>{{ money(shown.summary.fees) }} total fees</small>
        </div>
      </div>
      <div class="equity-header">
        <h3>Account equity over observed time</h3>
        <span
          >{{ shown.summary.completedBars }} completed bars ·
          {{ shown.summary.signals }} crosses ·
          {{ shown.summary.fills }} fills</span
        >
      </div>
      <svg
        v-if="shown.equity.length > 1"
        class="equity-chart"
        viewBox="0 0 960 145"
        role="img"
        aria-label="Simulated account equity curve in USD"
      >
        <line x1="25" y1="115" x2="935" y2="115" stroke="#334136" />
        <path :d="curve.path" fill="none" stroke="#b8df8c" stroke-width="2" />
        <text x="25" y="14">{{ money(curve.max) }}</text>
        <text x="25" y="140">{{ money(curve.min) }}</text>
        <text x="750" y="140">
          {{ money(shown.summary.equity) }} ending equity
        </text>
      </svg>
      <p v-else class="strategy-empty">
        Waiting for more quote receipts to draw the equity curve.
      </p>
      <div class="trade-tabs">
        <button
          :class="{ active: ledger === 'fills' }"
          @click="ledger = 'fills'"
        >
          Fills · {{ shown.fills.length }}</button
        ><button
          :class="{ active: ledger === 'orders' }"
          @click="ledger = 'orders'"
        >
          Orders &amp; decisions · {{ shown.orders.length }}
        </button>
      </div>
      <div class="trade-table-wrap">
        <table v-if="ledger === 'fills'" aria-label="Simulated fills">
          <thead>
            <tr>
              <th>ORDER / SIDE</th>
              <th>FILL SOURCE TIME</th>
              <th>QUANTITY</th>
              <th>EXECUTION PRICE</th>
              <th>FEE</th>
              <th>REALIZED P&amp;L</th>
              <th>SOURCE RECEIPT</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="f in [...shown.fills].reverse().slice(0, 30)"
              :key="f.receiptId"
            >
              <td>
                #{{ f.orderId }} ·
                <span :class="f.side === 'buy' ? 'positive' : 'negative'">{{
                  f.side.toUpperCase()
                }}</span>
              </td>
              <td>{{ when(f.sourceTime) }}</td>
              <td>{{ f.quantity }}</td>
              <td>{{ money(f.price) }}</td>
              <td>{{ money(f.fee) }}</td>
              <td>{{ money(f.realizedPnl) }}</td>
              <td>#{{ f.receiptId }} · obs #{{ f.quoteObservationId }}</td>
            </tr>
          </tbody>
        </table>
        <table v-else aria-label="Simulated orders">
          <thead>
            <tr>
              <th>ORDER / SIGNAL</th>
              <th>CANDLE SOURCE TIME</th>
              <th>DECIDED AT RECEIPT TIME</th>
              <th>DECISION RECEIPT</th>
              <th>OUTCOME</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="o in [...shown.orders].reverse().slice(0, 30)"
              :key="o.id"
            >
              <td>#{{ o.id }} · {{ o.side.toUpperCase() }}</td>
              <td>{{ when(o.signalTime) }}</td>
              <td>{{ when(o.decisionTime) }}</td>
              <td>#{{ o.signalReceiptId }}</td>
              <td>{{ o.status }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="!shown.orders.length" class="strategy-empty">
        No eligible crossover yet. The account stays in cash while it waits.
      </p>
      <p
        v-else-if="!shown.fills.length && ledger === 'fills'"
        class="strategy-empty"
      >
        No fills yet. Open Orders &amp; decisions to see pending or skipped
        signals.
      </p>
      <p class="experiment-description">
        {{ shown.processedReceipts.toLocaleString() }} receipts examined ·
        receipt watermark #{{ shown.untilReceipt }} · latest 30 rows shown ·
        saved experiment {{ shown.id.slice(0, 8) }}
      </p>
    </template>
    <p v-else class="strategy-empty">
      {{
        experiment === "backtest"
          ? "Run a backtest on your stored Yahoo observations to inspect the account and every simulated fill."
          : "Start a paper account to act on future completed candles. You can close the browser while the backend collects."
      }}
    </p>
    <details class="strategy-rules">
      <summary>Execution rules and what this result means</summary>
      <p>
        Long only. An upward confirmed crossover submits a buy using 95% of
        cash; a downward cross sells the position. Fills use the next fresh
        quote received after the decision, with adverse slippage and fees on
        both sides. One basis point is 0.01%. Quantities use eight decimals;
        cash and fees use cents.
      </p>
      <p>
        Forming candles are excluded. Late completed corrections remain in the
        market ledger; an account consumes each completed candle once and
        preserves its original decisions. Bootstrap bars warm up averages. A
        signal more than two minutes late is excluded; an unfilled order expires
        after five minutes.
      </p>
      <p>
        This backtest measures this fixed strategy on the saved observations and
        their actual receipt order. Missing quotes mean fewer fills. Gaps are
        retained; windows count observed completed bars. Final positions are
        marked to the last quote without forced liquidation. One chosen symbol
        risks selection bias; tuning windows on this sample risks overfitting.
        Market impact, bid/ask depth, taxes and real order routing are outside
        this simulation. Historical outcomes cannot establish future
        performance.
      </p>
    </details>
  </section>
</template>
