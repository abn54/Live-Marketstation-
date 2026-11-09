<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef, watch } from "vue";
import {
  Activity,
  ArrowDownLeft,
  ArrowUpRight,
  ChartCandlestick,
  ChevronRight,
  CircleHelp,
  Database,
  Expand,
  FileClock,
  Globe2,
  Layers3,
  Pause,
  Play,
  Radio,
  RotateCcw,
  ShieldCheck,
  Unplug,
  Wifi,
} from "@lucide/vue";
import MarketChart from "./MarketChart.vue";
import type {
  Feed,
  Observation,
  Receipt,
  ReplayRecord,
  Stats,
  SymbolData,
} from "./types";
const symbols = ["BTC-USD", "ETH-USD", "SPY", "AAPL"];
const names: Record<string, string> = {
  "BTC-USD": "Bitcoin",
  "ETH-USD": "Ethereum",
  SPY: "S&P 500 ETF",
  AAPL: "Apple Inc.",
};
const blank = (symbol: string): SymbolData => ({
  symbol,
  candles: [],
  quote: null,
  receipts: [],
});
const data = shallowRef<Record<string, SymbolData>>({});
const selected = ref("BTC-USD");
const feed = shallowRef<Feed>({
  stream: { state: "connecting", detail: "Connecting to FastAPI" },
  chart: { state: "connecting", detail: "Waiting for candles" },
  paused: false,
  pollMs: 15000,
  symbols: {},
});
const stats = shallowRef<Stats>({
  observations: 0,
  revisions: 0,
  receipts: 0,
  duplicates: 0,
  superseded: 0,
  candles: 0,
  lastReceiptId: 0,
  journalMode: "wal",
});
const connected = ref(false),
  now = ref(Date.now()),
  demo = ref(false),
  mode = ref<"live" | "replay">("live"),
  fitKey = ref(0),
  help = ref(false),
  tab = ref<"observations" | "pipeline">("observations"),
  error = ref(""),
  replayLoading = ref(false),
  feedPending = ref(false);
const chartPanel = ref<HTMLElement | null>(null),
  evidencePanel = ref<HTMLElement | null>(null);
const records = shallowRef<ReplayRecord[]>([]),
  checkpoint = shallowRef<Pick<SymbolData, "candles" | "quote">>({
    candles: [],
    quote: null,
  }),
  cursor = ref(0),
  playing = ref(false),
  speed = ref(4);
let replayRequest: AbortController | undefined,
  disposed = false,
  socket: WebSocket | undefined,
  reconnectTimer: ReturnType<typeof setTimeout> | undefined,
  clockTimer: ReturnType<typeof setInterval> | undefined;
const money = (v?: number) =>
  v === undefined
    ? "—"
    : v.toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
const count = (v: number) => v.toLocaleString("en-US");
const time = (v?: number) =>
  v
    ? new Date(v).toLocaleTimeString("en-US", {
        hour12: false,
        timeZone: "UTC",
      }) + " UTC"
    : "—";
const iso = (v?: number) => (v ? new Date(v).toISOString() : "");
const age = (v: number | undefined) =>
  !v
    ? "No observation"
    : Math.max(0, Math.floor((now.value - v) / 1000)) < 60
      ? `${Math.max(0, Math.floor((now.value - v) / 1000))}s ago`
      : `${Math.floor((now.value - v) / 60000)}m ago`;
function apply(old: SymbolData, o: Observation): SymbolData {
  if (o.kind === "candle")
    return {
      ...old,
      candles: [...old.candles.filter((x) => x.logicalId !== o.logicalId), o]
        .sort((a, b) => a.sourceTime - b.sourceTime)
        .slice(-360),
    };
  return !old.quote || o.sourceTime >= old.quote.sourceTime
    ? { ...old, quote: o }
    : old;
}
function connect() {
  if (disposed) return;
  const current = new WebSocket(
    `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws`,
  );
  socket = current;
  const snapshotTimer = setTimeout(() => current.close(), 10000);
  current.onclose = () => {
    clearTimeout(snapshotTimer);
    if (current !== socket) return;
    connected.value = false;
    if (!disposed) reconnectTimer = setTimeout(connect, 1500);
  };
  current.onerror = () => current.close();
  current.onmessage = (e) => {
    if (current !== socket || disposed) return;
    const m = JSON.parse(e.data);
    if (m.status) feed.value = m.status;
    if (m.stats) stats.value = m.stats;
    if (m.type === "snapshot") {
      clearTimeout(snapshotTimer);
      demo.value = m.demoControls;
      data.value = Object.fromEntries(
        m.symbols.map((s: SymbolData) => [s.symbol, s]),
      );
      connected.value = true;
    }
    if (m.type === "observations") {
      const next = { ...data.value };
      for (const r of m.results) {
        const o = r.observation as Observation;
        let s = next[o.symbol] ?? blank(o.symbol);
        if (r.applied) s = apply(s, o);
        next[o.symbol] = {
          ...s,
          receipts: [
            {
              ...o,
              receiptId: r.receiptId,
              receiptTime: r.receivedAt,
              disposition: r.disposition,
            },
            ...s.receipts,
          ].slice(0, 12),
        };
      }
      data.value = next;
    }
  };
}
onMounted(() => {
  connect();
  clockTimer = setInterval(() => (now.value = Date.now()), 1000);
});
onUnmounted(() => {
  disposed = true;
  replayRequest?.abort();
  clearTimeout(reconnectTimer);
  clearInterval(clockTimer);
  socket?.close();
});
watch(
  selected,
  (symbol, _, onCleanup) => {
    const c = new AbortController();
    onCleanup(() => c.abort());
    fetch(`/api/receipts?symbol=${symbol}`, { signal: c.signal })
      .then((r) => r.json())
      .then((d) => {
        if (!d.receipts) return;
        const s = data.value[symbol] ?? blank(symbol);
        const receipts = [
          ...new Map(
            [...s.receipts, ...d.receipts].map((r: Receipt) => [
              r.receiptId,
              r,
            ]),
          ).values(),
        ]
          .sort((a, b) => b.receiptId - a.receiptId)
          .slice(0, 12);
        data.value = { ...data.value, [symbol]: { ...s, receipts } };
      })
      .catch(() => {});
  },
  { immediate: true },
);
watch([playing, speed, mode], (_, __, onCleanup) => {
  if (!playing.value || mode.value !== "replay") return;
  const t = setInterval(
    () => (cursor.value = Math.min(cursor.value + 1, records.value.length)),
    1000 / speed.value,
  );
  onCleanup(() => clearInterval(t));
});
watch([cursor, () => records.value.length], () => {
  if (cursor.value >= records.value.length) playing.value = false;
});
const replayData = computed(() => {
  const heads = new Map(checkpoint.value.candles.map((o) => [o.logicalId, o]));
  let quote = checkpoint.value.quote;
  for (const r of records.value.slice(0, cursor.value)) {
    const o = r.observation;
    if (!r.applied) continue;
    if (o.kind === "candle") heads.set(o.logicalId, o);
    else if (!quote || o.sourceTime >= quote.sourceTime) quote = o;
  }
  return {
    symbol: selected.value,
    candles: [...heads.values()]
      .sort((a, b) => a.sourceTime - b.sourceTime)
      .slice(-360),
    quote,
    receipts: records.value
      .slice(Math.max(0, cursor.value - 12), cursor.value)
      .reverse()
      .map((r) => ({
        ...r.observation,
        receiptId: r.receiptId,
        receiptTime: r.receivedAt,
        disposition: r.disposition,
      })),
  };
});
const live = computed(
  () => data.value[selected.value] ?? blank(selected.value),
);
const shown = computed(() =>
  mode.value === "replay" ? replayData.value : live.value,
);
const last = computed(() => shown.value.candles.at(-1));
const quote = computed(() => shown.value.quote);
const price = computed(() => quote.value?.price ?? last.value?.close);
const change = computed(
  () =>
    quote.value?.changePercent ??
    (shown.value.candles[0] && price.value
      ? (price.value / shown.value.candles[0].open! - 1) * 100
      : 0),
);
const meta = computed(() => feed.value.symbols[selected.value]);
const quoteStale = computed(
  () => !live.value.quote || now.value - live.value.quote.sourceTime > 60000,
);
const candleStale = computed(
  () =>
    !live.value.candles.at(-1) ||
    now.value - live.value.candles.at(-1)!.sourceTime > 180000,
);
const feedUnavailable = computed(
  () =>
    feed.value.paused ||
    meta.value?.chartState === "unavailable" ||
    feed.value.stream.state === "unavailable",
);
const collectorGood = computed(
  () =>
    connected.value &&
    !feedUnavailable.value &&
    feed.value.stream.state === "streaming" &&
    meta.value?.chartState === "available" &&
    !!meta.value?.lastQuoteReceivedAt &&
    meta.value?.lastQuoteSourceTime === live.value.quote?.sourceTime &&
    !quoteStale.value &&
    !candleStale.value,
);
const good = computed(() => mode.value === "live" && collectorGood.value);
const statusLabel = computed(() =>
  mode.value === "replay"
    ? "RECORDED REPLAY"
    : !connected.value
      ? "SERVER OFFLINE"
      : feedUnavailable.value
        ? "FEED UNAVAILABLE"
        : !collectorGood.value
          ? "WAITING / STALE"
          : "LIVE FEED",
);
const ohlc = computed(
  () =>
    [
      ["O", last.value?.open],
      ["H", last.value?.high],
      ["L", last.value?.low],
      ["C", last.value?.close],
    ] as const,
);
async function startReplay() {
  if (replayLoading.value) return;
  replayLoading.value = true;
  error.value = "";
  playing.value = false;
  const request = new AbortController();
  replayRequest = request;
  try {
    const r = await fetch(`/api/replay/recent?symbol=${selected.value}`, {
      signal: request.signal,
    });
    if (!r.ok) throw new Error("Replay could not be loaded");
    const recording = await r.json();
    if (replayRequest !== request) return;
    if (!recording.records.length)
      throw new Error("No recorded observations for this symbol yet");
    checkpoint.value = recording.checkpoint;
    records.value = recording.records;
    cursor.value = Math.max(0, records.value.length - 80);
    mode.value = "replay";
    playing.value = true;
  } catch (e) {
    if (replayRequest === request) error.value = (e as Error).message;
  } finally {
    if (replayRequest === request) {
      replayRequest = undefined;
      replayLoading.value = false;
    }
  }
}
async function toggleFeed() {
  feedPending.value = true;
  error.value = "";
  try {
    const r = await fetch("/api/demo/feed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: feed.value.paused ? "reconnect" : "disconnect",
      }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error ?? "Feed control failed");
    // While connected, WebSocket events deliver feed status in server order.
    if (!connected.value) feed.value = d.feed;
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    feedPending.value = false;
  }
}
function choose(symbol: string) {
  selected.value = symbol;
  goLive();
  records.value = [];
  checkpoint.value = { candles: [], quote: null };
  cursor.value = 0;
  error.value = "";
}
function goLive() {
  replayRequest?.abort();
  replayRequest = undefined;
  replayLoading.value = false;
  mode.value = "live";
  playing.value = false;
}
function showChart() {
  chartPanel.value?.scrollIntoView({ block: "start" });
}
function showEvidence(view: typeof tab.value) {
  tab.value = view;
  evidencePanel.value?.scrollIntoView({ block: "start" });
}
function toggleReplay() {
  if (cursor.value >= records.value.length) cursor.value = 0;
  playing.value = !playing.value;
}
</script>

<template>
  <div class="shell">
    <aside class="rail">
      <a class="brandmark" href="/" aria-label="Marketstation home"
        ><Activity :size="24"
      /></a>
      <div class="rail-line" />
      <button
        class="rail-button active"
        title="Market dashboard"
        aria-label="Market dashboard"
        @click="
          goLive();
          tab = 'observations';
          showChart();
        "
      >
        <ChartCandlestick :size="21" />
      </button>
      <button
        class="rail-button"
        title="Recorded replay"
        aria-label="Recorded replay"
        :disabled="replayLoading"
        @click="
          showChart();
          startReplay();
        "
      >
        <FileClock :size="21" />
      </button>
      <button
        class="rail-button"
        title="View observation ledger"
        aria-label="View observation ledger"
        @click="showEvidence('observations')"
      >
        <Activity :size="21" />
      </button>
      <button
        class="rail-button"
        title="Data pipeline"
        aria-label="Data pipeline"
        @click="showEvidence('pipeline')"
      >
        <Database :size="21" />
      </button>
      <div class="rail-bottom">
        <button
          class="rail-button"
          aria-label="About this workstation"
          @click="help = !help"
        >
          <CircleHelp :size="20" />
        </button>
        <div class="avatar">AN</div>
      </div>
    </aside>
    <div class="workspace">
      <header class="topbar">
        <div class="wordmark">
          marketstation<span class="brand-dot">.</span
          ><span class="edition">VUE / FASTAPI / SQLITE</span>
        </div>
        <div class="top-right">
          <span class="desktop-clock">{{ time(now) }}</span
          ><span :class="['connection', { bad: !connected }]"
            ><span class="dot" />{{
              connected ? "Server connected" : "Reconnecting to server"
            }}</span
          >
        </div>
      </header>
      <main>
        <div class="page-heading">
          <div>
            <div class="eyebrow">THE MARKET, IN MOTION</div>
            <h1>Market overview<span class="heading-dot">.</span></h1>
            <p>A live view. A lasting record.</p>
          </div>
          <div class="heading-actions">
            <span
              :class="[
                'status-pill',
                good ? 'good' : mode === 'replay' ? 'replay' : 'warning',
              ]"
              ><span class="dot" />{{ statusLabel }}</span
            ><span class="source-tag"><Globe2 :size="13" />Yahoo Finance</span>
          </div>
        </div>
        <div v-if="help" class="notice">
          Part 4.1 · Vue 3 + FastAPI + SQLite. Yahoo quotes stream over
          WebSockets; one-minute OHLCV is fetched every
          {{ feed.pollMs / 1000 }}s and streamed after a SQLite commit. Times
          are UTC. Replay is recorded and read-only. TradingView Lightweight
          Charts™ · Copyright (с) 2025 TradingView, Inc.
        </div>
        <div v-if="error" class="notice warning" role="alert">{{ error }}</div>
        <div class="watchlist">
          <button
            v-for="s in symbols"
            :key="s"
            :class="['watch-card', { selected: selected === s }]"
            @click="choose(s)"
          >
            <span
              :class="[
                'coin-icon',
                { eth: s === 'ETH-USD', spy: s === 'SPY', apple: s === 'AAPL' },
              ]"
              >{{
                s === "BTC-USD"
                  ? "₿"
                  : s === "ETH-USD"
                    ? "Ξ"
                    : s === "SPY"
                      ? "S"
                      : "A"
              }}</span
            >
            <span class="watch-name"
              ><strong>{{ s }}</strong
              ><small>{{ names[s] }}</small></span
            >
            <span class="watch-values"
              ><strong
                >${{
                  money(data[s]?.quote?.price ?? data[s]?.candles.at(-1)?.close)
                }}</strong
              ><small
                :class="
                  (data[s]?.quote?.changePercent ?? 0) >= 0
                    ? 'positive'
                    : 'negative'
                "
                >{{
                  data[s]?.quote?.changePercent == null
                    ? "Recorded candles"
                    : `${data[s]!.quote!.changePercent! >= 0 ? "+" : ""}${data[s]!.quote!.changePercent!.toFixed(2)}%`
                }}</small
              ></span
            ><span v-if="selected === s" class="selected-indicator" />
          </button>
        </div>
        <div class="dashboard-grid">
          <section ref="chartPanel" class="panel chart-panel">
            <div class="instrument-header">
              <div class="instrument-title">
                <h2>{{ names[selected] }}<span>/ USD</span></h2>
                <span class="asset-label"
                  >{{ selected.includes("USD") ? "CRYPTO" : "EQUITY"
                  }}<span>•</span>{{ meta?.exchange ?? "Yahoo Finance" }}</span
                >
              </div>
              <div class="mode-toggle">
                <button :class="{ on: mode === 'live' }" @click="goLive">
                  <Radio :size="13" />Live</button
                ><button
                  :class="{ on: mode === 'replay' }"
                  :disabled="replayLoading"
                  @click="startReplay"
                >
                  <FileClock :size="13" />{{ replayLoading ? "Loading…" : "Replay" }}
                </button>
              </div>
            </div>
            <div v-if="demo" class="demo-bar">
              <span :class="{ amber: !collectorGood }" aria-live="polite">{{
                feedUnavailable ? "Yahoo unavailable · saved chart" :
                collectorGood ? "Yahoo source live" : "Waiting for Yahoo"
              }}</span>
              <button :disabled="feedPending || !connected" @click="toggleFeed">
                <Wifi v-if="feed.paused" :size="13" /><Unplug v-else :size="13" />{{
                  feed.paused ? "Reconnect Yahoo feed" : "Demonstrate feed outage"
                }}
              </button>
            </div>
            <div class="price-row">
              <strong class="big-price">${{ money(price) }}</strong
              ><span
                :class="['price-change', change >= 0 ? 'positive' : 'negative']"
                ><ArrowUpRight v-if="change >= 0" :size="16" /><ArrowDownLeft
                  v-else
                  :size="16"
                />{{ change >= 0 ? "+" : "" }}{{ change.toFixed(2) }}%<small>{{
                  quote ? "Yahoo change" : "visible window"
                }}</small></span
              ><span class="price-time"
                >{{
                  mode === "replay"
                    ? "Recorded source time"
                    : "Quote source time"
                }}<b :title="iso(quote?.sourceTime ?? last?.sourceTime)">{{
                  time(quote?.sourceTime ?? last?.sourceTime)
                }}</b></span
              >
            </div>
            <div class="chart-toolbar">
              <div class="interval-selector">
                <span class="interval-active">1m</span
                ><span>ONE-MINUTE CANDLES</span>
              </div>
              <div class="chart-legend">
                <span><i class="legend-line" />Price</span
                ><span><i class="legend-bar" />Volume</span
                ><button
                  aria-label="Fit chart to data"
                  title="Fit chart"
                  @click="fitKey++"
                >
                  <Expand :size="15" />
                </button>
              </div>
            </div>
            <div class="ohlc-strip">
              <span v-for="[k, v] in ohlc" :key="k"
                ><small>{{ k }}</small
                >{{ money(v) }}</span
              ><span class="candle-state"
                ><span :class="['dot', { 'muted-dot': last?.complete }]" />{{
                  last
                    ? last.complete
                      ? "Complete candle"
                      : "Forming candle"
                    : "Awaiting candles"
                }}</span
              >
            </div>
            <div class="chart-wrap">
              <MarketChart
                :candles="shown.candles"
                :symbol="`${selected}:${mode}`"
                :fit-key="fitKey"
              />
              <div v-if="!shown.candles.length" class="chart-empty">
                <ChartCandlestick :size="28" /><strong>{{
                  mode === "replay"
                    ? "Waiting for the first recorded candle"
                    : "Waiting for Yahoo candles"
                }}</strong
                ><span>{{
                  meta?.chartError ??
                  "Observations appear here after they are committed to SQLite."
                }}</span>
              </div>
              <div v-if="mode === 'replay'" class="replay-watermark">
                RECORDED
              </div>
            </div>
            <div class="chart-footer">
              <span
                ><span :class="['dot', { 'muted-dot': !good }]" />{{
                  mode === "replay"
                    ? "SQLite recording"
                    : feedUnavailable
                      ? "Upstream unavailable · retained data"
                      : `Yahoo Chart · ${feed.pollMs / 1000}s refresh`
                }}<b>OHLCV</b></span
              ><span
                >Vol
                {{ last?.volume == null ? "unreported" : count(last.volume) }} ·
                UTC</span
              >
            </div>
            <div v-if="mode === 'replay'" class="replay-controls">
              <button
                :aria-label="playing ? 'Pause replay' : 'Play replay'"
                @click="toggleReplay"
              >
                <Pause v-if="playing" :size="16" /><Play
                  v-else
                  :size="16"
                /></button
              ><button
                aria-label="Restart replay"
                @click="
                  cursor = 0;
                  playing = true;
                "
              >
                <RotateCcw :size="15" /></button
              ><input
                aria-label="Replay position"
                type="range"
                min="0"
                :max="records.length"
                v-model.number="cursor"
                @input="playing = false"
              /><span :title="`${records.length} recent saved receipts`">{{ cursor }} / {{ records.length }}</span
              ><select aria-label="Replay speed" v-model.number="speed">
                <option :value="1">1 receipt/s</option>
                <option :value="4">4 receipts/s</option>
                <option :value="20">20 receipts/s</option>
                <option :value="100">100 receipts/s</option>
              </select>
            </div>
          </section>
          <aside class="right-stack">
            <section class="panel feed-panel">
              <div class="panel-heading">
                <h3><Radio :size="15" />Feed health</h3>
                <span class="tiny-tag">LIVE SOURCE</span>
              </div>
              <div :class="['feed-health', { amber: !collectorGood }]">
                <span class="pulse-dot" />
                <div>
                  <strong>{{
                    feed.paused
                      ? "Upstream disconnected"
                      : !connected
                        ? "Server disconnected"
                        : collectorGood
                          ? "Receiving market data"
                          : feedUnavailable
                            ? "Feed needs attention"
                            : "Waiting for fresh data"
                  }}</strong
                  ><small>{{
                    feed.paused
                      ? "Intentional outage demonstration"
                      : mode === "replay"
                        ? "Live collection continues during replay"
                        : feed.stream.detail
                  }}</small>
                </div>
              </div>
              <dl class="key-values">
                <div>
                  <dt>Provider</dt>
                  <dd>Yahoo Finance<ArrowUpRight :size="11" /></dd>
                </div>
                <div>
                  <dt>Quote age</dt>
                  <dd :class="{ amber: quoteStale }">
                    {{ age(live.quote?.sourceTime) }}
                  </dd>
                </div>
                <div>
                  <dt>Candle age</dt>
                  <dd :class="{ amber: candleStale }">
                    {{ age(live.candles.at(-1)?.sourceTime) }}
                  </dd>
                </div>
                <div>
                  <dt>Last receipt</dt>
                  <dd>
                    {{
                      age(
                        Math.max(
                          meta?.lastQuoteReceivedAt ?? 0,
                          meta?.lastChartReceivedAt ?? 0,
                        ) || undefined,
                      )
                    }}
                  </dd>
                </div>
                <div>
                  <dt>Yahoo socket</dt>
                  <dd
                    :class="
                      feed.stream.state === 'streaming' ? 'positive' : 'amber'
                    "
                  >
                    {{ feed.stream.state }}
                  </dd>
                </div>
                <div>
                  <dt>Candle endpoint</dt>
                  <dd
                    :class="
                      meta?.chartState === 'available' ? 'positive' : 'amber'
                    "
                  >
                    {{ meta?.chartState ?? "connecting" }}
                  </dd>
                </div>
              </dl>
              <div v-if="meta?.chartError" class="inline-error">
                {{ meta.chartError }}
              </div>
              <div class="health-note">
                <ShieldCheck :size="14" /><span
                  >Source time and receipt time tracked separately.</span
                >
              </div>
            </section>
            <section class="panel storage-panel">
              <div class="panel-heading">
                <h3><Database :size="15" />Persistent by design</h3>
                <span class="sqlite-tag">SQLite</span>
              </div>
              <div class="record-count">
                {{ count(stats.observations) }}<span>stored observations</span>
              </div>
              <div class="storage-grid">
                <div>
                  <b>{{ count(stats.revisions) }}</b
                  ><span>revisions</span>
                </div>
                <div>
                  <b>{{ count(stats.duplicates) }}</b
                  ><span>duplicates</span>
                </div>
                <div>
                  <b>{{ count(stats.candles) }}</b
                  ><span>candles</span>
                </div>
              </div>
              <div class="commit-line">
                <span class="dot" />Committed before broadcast<span
                  class="wal-tag"
                  >WAL</span
                >
              </div>
              <button class="full-button" @click="showEvidence('observations')">
                <Activity :size="14" />View observation ledger<ChevronRight :size="15" />
              </button>
            </section>
            <section class="session-note">
              <span class="eyebrow">BUILT TO BE TRACEABLE</span>
              <p>
                Every update has a source.<br />Every revision leaves a record.
              </p>
              <div>
                <Layers3 :size="14" />Part 4.1 · Market data &amp; dashboard
              </div>
            </section>
          </aside>
        </div>
        <section ref="evidencePanel" class="panel evidence-panel">
          <div class="evidence-tabs">
            <div>
              <button
                :class="{ active: tab === 'observations' }"
                @click="tab = 'observations'"
              >
                <Activity :size="14" />Observation ledger<span>{{
                  shown.receipts.length
                }}</span></button
              ><button
                :class="{ active: tab === 'pipeline' }"
                @click="tab = 'pipeline'"
              >
                <Layers3 :size="14" />Data pipeline
              </button>
            </div>
            <span class="ledger-label">{{
              mode === "replay"
                ? "RECORDED RECEIPTS"
                : "LATEST PERSISTED RECEIPTS"
            }}</span>
          </div>
          <div v-if="tab === 'observations'" class="table-scroll">
            <table role="table" aria-label="Observation ledger">
              <thead>
                <tr>
                  <th>RECEIPT / IDENTITY</th>
                  <th>SOURCE</th>
                  <th>SOURCE TIME</th>
                  <th>RECEIVED</th>
                  <th>VALUE</th>
                  <th>REVISION</th>
                  <th>STATE</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in shown.receipts.slice(0, 5)" :key="r.receiptId">
                  <td>
                    <span class="receipt-number">#{{ r.receiptId }}</span
                    ><span :title="r.logicalId" class="identity"
                      >{{ r.symbol }} · {{ r.interval }}</span
                    ><span class="observation-number">Obs. #{{ r.id }}</span>
                  </td>
                  <td data-label="Source">
                    <span class="source-cell"
                      ><span class="dot muted-dot" />{{ r.source }}</span
                    >
                  </td>
                  <td data-label="Source time" :title="iso(r.sourceTime)">{{ time(r.sourceTime) }}</td>
                  <td data-label="Received" :title="iso(r.receiptTime)">{{ time(r.receiptTime) }}</td>
                  <td data-label="Value">${{ money(r.price ?? r.close) }}</td>
                  <td data-label="Revision">
                    <span class="revision">v{{ r.revision }}</span>
                  </td>
                  <td>
                    <span :class="['disposition', r.disposition]"
                      >{{
                        r.kind === "candle" ? (r.complete ? "complete · " : "forming · ") : ""
                      }}{{ r.disposition }}</span
                    >
                  </td>
                </tr>
                <tr v-if="!shown.receipts.length">
                  <td colspan="7" class="empty-ledger">
                    Waiting for persisted observations. No generated prices are
                    used.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="pipeline">
            <div>
              <Globe2 /><strong>01 · Yahoo Finance</strong
              ><span>WebSocket quotes + chart OHLCV</span>
            </div>
            <ChevronRight />
            <div>
              <Database /><strong>02 · SQLite commit</strong
              ><span
                >{{ count(stats.receipts) }} receipts · revisions
                preserved</span
              >
            </div>
            <ChevronRight />
            <div>
              <Wifi /><strong>03 · FastAPI WebSocket</strong
              ><span
                >{{
                  connected ? "Browser connected" : "Browser reconnecting"
                }}
                · /ws</span
              >
            </div>
            <ChevronRight />
            <div>
              <ChartCandlestick /><strong>04 · Vue live chart</strong
              ><span>{{ shown.candles.length }} one-minute candles</span>
            </div>
          </div>
        </section>
        <footer class="page-footer">
          <span
            ><Activity :size="12" />MARKETSTATION<span>/</span>Live data.
            Recorded faithfully.</span
          >
          <div>
            <a
              href="https://www.tradingview.com/"
              target="_blank"
              rel="noreferrer"
              >Charts by TradingView ↗</a
            ><a
              href="https://github.com/abn54/Live-Marketstation-"
              target="_blank"
              rel="noreferrer"
              >View source ↗</a
            >
          </div>
        </footer>
      </main>
    </div>
  </div>
</template>
