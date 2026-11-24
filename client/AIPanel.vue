<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import {
  Bot,
  MessageCircle,
  ScanLine,
  Mic,
  MicOff,
  ShieldCheck,
  Play,
  Pause,
  RefreshCw,
} from "@lucide/vue";
import { RealtimeVoice } from "./voice";
import type { VoiceState } from "./voice";

type Account = {
  cash: number;
  equity: number;
  quantity: string;
  realizedPnl: number;
  unrealizedPnl: number;
  fees: number;
  markPrice: string | null;
};
type Order = {
  id: number;
  side: string;
  status: string;
  decisionTime: number;
  activityId: number;
};
type Fill = { orderId: number; quantity: string; price: number; fee: number };
type BotState = {
  id: string;
  running: boolean;
  account: Account;
  orders: Order[];
  fills: Fill[];
  config: { fast: number; slow: number };
  autoCalls: number;
  autoUntil: number;
};
type Activity = {
  id: number;
  kind: string;
  createdAt: number;
  status: string;
  context: unknown;
  response: {
    text?: string;
    model?: string;
    reason?: string;
    question?: string;
    evidence?: string;
    decision?: { action: string; confidence: number; reason: string };
    checks?: { name: string; passed: boolean; detail: string }[];
  };
};
type State = {
  configured: boolean;
  model: string;
  visionModel?: string;
  audioModel: string;
  serviceStatus?: string;
  serviceError?: string;
  demoControls: boolean;
  bot: BotState | null;
  activities: Activity[];
  context: {
    capturedAt: number;
    market: { dataMode: string; quoteAgeMs: number | null };
    indicators: {
      candidate: string;
      fastLength: number;
      slowLength: number;
      latest: { fast: number | null; slow: number | null } | null;
    };
  };
};
const props = defineProps<{
  symbol: string;
  fast: number;
  slow: number;
  replay: boolean;
  captureChart: () => string;
}>();
const state = ref<State | null>(null),
  error = ref(""),
  connectionError = ref(""),
  busy = ref(false),
  interactionBusy = ref(false);
const activeTab = ref<"chat" | "vision" | "voice">("chat"),
  message = ref(""),
  image = ref("");
const audio = ref<HTMLAudioElement | null>(null),
  voiceState = ref<VoiceState>("idle"),
  voiceDetail = ref("Microphone off. Start a live conversation when ready.");
const transcripts = ref<{ role: string; text: string }[]>([]),
  voiceCapturedAt = ref(0);
let timer: ReturnType<typeof setInterval> | undefined,
  voice: RealtimeVoice | undefined,
  generation = 0,
  disposed = false;
const money = (value?: number | null) =>
  value == null
    ? "—"
    : value.toLocaleString("en-US", { style: "currency", currency: "USD" });
const time = (value: number) =>
  new Date(value).toLocaleTimeString("en-US", {
    timeZone: "UTC",
    hour12: false,
  }) + " UTC";
const decision = computed(() =>
  state.value?.activities.find((a) => a.kind === "decision"),
);
const conversations = computed(() =>
  [...(state.value?.activities ?? [])]
    .filter((a) => a.kind === "chat")
    .reverse()
    .slice(-4),
);
const vision = computed(() =>
  state.value?.activities.find((a) => a.kind === "vision"),
);
const lastAudioEvents = computed(() =>
  state.value?.activities.filter((a) => a.kind === "audio").slice(0, 3),
);

async function api<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(40000),
  });
  const result = await response.json().catch(() => {
    throw new Error("Server connection interrupted. Reconnect and try again.");
  });
  if (!response.ok)
    throw new Error(
      typeof result.error === "string"
        ? result.error
        : typeof result.detail === "string"
          ? result.detail
          : "Check the request and try again.",
    );
  return result as T;
}
async function refresh() {
  const requested = props.symbol,
    version = generation;
  try {
    const result = await api<State>(
      `/api/ai/status?symbol=${encodeURIComponent(requested)}`,
    );
    if (!disposed && version === generation && requested === props.symbol) {
      state.value = result;
      connectionError.value = "";
    }
  } catch (e) {
    if (!disposed && version === generation)
      connectionError.value =
        e instanceof Error ? e.message : "Server unavailable";
  }
}
async function ensureBot() {
  if (state.value?.bot) return state.value.bot;
  const result = await api<BotState>("/api/ai/bots", {
    symbol: props.symbol,
    fast: props.fast,
    slow: props.slow,
  });
  if (state.value) state.value.bot = result;
  return result;
}
async function act(action: "decision" | "review" | "control") {
  busy.value = true;
  error.value = "";
  try {
    const bot = await ensureBot();
    if (action === "control")
      await api(`/api/ai/bots/${bot.id}/control`, { running: !bot.running });
    else
      await api("/api/ai/decision", {
        botId: bot.id,
        requestId: crypto.randomUUID(),
        execute: action === "decision",
      });
    await refresh();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Decision check failed";
  } finally {
    busy.value = false;
  }
}
async function pauseBot() {
  const bot = state.value?.bot;
  if (!bot) return;
  try {
    await api(`/api/ai/bots/${bot.id}/control`, { running: false });
    await refresh();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Could not pause the bot";
  }
}
async function ask(prompt = message.value) {
  if (!prompt.trim()) return;
  interactionBusy.value = true;
  error.value = "";
  try {
    const history = conversations.value
      .filter((a) => a.status === "completed")
      .flatMap((a) => [
        { role: "user", content: (a.response.question ?? "").slice(0, 4000) },
        { role: "assistant", content: (a.response.text ?? "").slice(0, 4000) },
      ])
      .slice(-6);
    await api("/api/ai/chat", {
      symbol: props.symbol,
      message: prompt,
      history,
    });
    message.value = "";
    await refresh();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Chat unavailable";
  } finally {
    interactionBusy.value = false;
  }
}
async function analyze() {
  interactionBusy.value = true;
  error.value = "";
  try {
    image.value = props.captureChart();
    await api("/api/ai/vision", {
      symbol: props.symbol,
      image: image.value,
      message:
        "Explain the trend, SMA lines and visible crossover markers. What does this image establish, and what does it leave uncertain?",
    });
    await refresh();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Chart analysis unavailable";
  } finally {
    interactionBusy.value = false;
  }
}
async function startVoice() {
  transcripts.value = [];
  voiceCapturedAt.value = Date.now();
  await voice?.start(props.symbol);
}
onMounted(() => {
  void refresh();
  timer = setInterval(() => void refresh(), 4000);
  if (audio.value)
    voice = new RealtimeVoice(audio.value, {
      onState: (value, detail) => {
        voiceState.value = value;
        voiceDetail.value = detail;
      },
      onTranscript: (role, text) => {
        if (typeof text === "string")
          transcripts.value = [...transcripts.value, { role, text }].slice(-8);
      },
      onEvent: (sessionId, value, detail) => {
        void api("/api/ai/audio-events", { sessionId, state: value, detail })
          .then(refresh)
          .catch(() => {});
      },
    });
});
watch(
  () => props.symbol,
  () => {
    generation++;
    state.value = null;
    image.value = "";
    message.value = "";
    error.value = "";
    voice?.stop("Symbol changed. Start a new conversation for this symbol.");
    transcripts.value = [];
    void refresh();
  },
);
watch(activeTab, (value, previous) => {
  if (previous === "voice" && value !== "voice")
    voice?.stop("Voice stopped when leaving the conversation tab.");
});
const pageLeave = () => voice?.stop();
onMounted(() => window.addEventListener("pagehide", pageLeave));
onUnmounted(() => {
  disposed = true;
  generation++;
  clearInterval(timer);
  voice?.stop();
  window.removeEventListener("pagehide", pageLeave);
});
</script>

<template>
  <section
    class="panel ai-panel"
    aria-label="AI-assisted trading and interaction"
  >
    <header class="ai-heading">
      <div>
        <span class="eyebrow">PART 4.3 · AI WORKSTATION</span>
        <h2>Understand. Check. Simulate.</h2>
        <p>
          Market context, a checked decision, and a traceable simulated outcome.
        </p>
      </div>
      <span :class="['ai-provider', { ready: state?.configured }]">{{
        !state
          ? "Connecting to the workstation…"
          : state.configured
            ? state.model
            : "Live AI needs an API key"
      }}</span>
    </header>
    <p v-if="error || connectionError" class="ai-error" role="alert">
      {{ error || connectionError }}
    </p>
    <p v-if="state?.serviceError" class="ai-error" role="status">
      {{ state.serviceError }}
    </p>
    <div v-if="state && !state.configured" class="ai-notice">
      Live AI is unavailable until the server’s private Gemini key for a
      confirmed Free tier project is configured. Existing market data, replay
      and SMA simulations still work.
    </div>
    <div class="ai-layout">
      <div class="ai-bot">
        <div class="ai-title">
          <Bot :size="22" />
          <h3>Simulated decision bot</h3>
          <span class="ai-pill">{{
            state?.bot?.running ? "AUTO ON" : "AUTO OFF"
          }}</span>
        </div>
        <p class="ai-caption">
          SMA {{ state?.bot?.config.fast ?? fast }} /
          {{ state?.bot?.config.slow ?? slow }} sets the candidate. AI may
          approve it or hold. Every action passes server checks.
        </p>
        <div class="ai-signal">
          <div>
            <small>SMA candidate</small
            ><strong>{{
              state?.context.indicators.candidate.toUpperCase() ?? "—"
            }}</strong>
          </div>
          <div>
            <small>Market context</small
            ><strong>{{ state?.context.market.dataMode ?? "Loading" }}</strong>
          </div>
          <div>
            <small>Quote age</small
            ><strong>{{
              state?.context.market.quoteAgeMs == null
                ? "—"
                : Math.max(
                    0,
                    Math.round(state.context.market.quoteAgeMs / 1000),
                  ) + "s"
            }}</strong>
          </div>
        </div>
        <div class="ai-actions">
          <button
            class="ai-primary"
            :disabled="busy || !state?.configured || replay"
            @click="act('decision')"
          >
            <ShieldCheck :size="17" />{{
              busy ? "Checking…" : "Check decision"
            }}</button
          ><button
            class="ai-secondary"
            :disabled="
              (busy && !state?.bot?.running) || !state?.configured || replay
            "
            @click="state?.bot?.running ? pauseBot() : act('control')"
          >
            <Pause v-if="state?.bot?.running" :size="17" /><Play
              v-else
              :size="17"
            />{{ state?.bot?.running ? "Pause bot" : "Start auto bot" }}</button
          ><button
            class="ai-link"
            :disabled="busy || !state?.configured"
            @click="act('review')"
          >
            Review only</button
          ><button
            v-if="
              state?.bot &&
              (busy ||
                state.bot.orders.some((o) => o.status === 'pending next quote'))
            "
            class="ai-link"
            @click="pauseBot()"
          >
            Cancel pending action
          </button>
        </div>
        <p class="ai-caption">
          {{
            state?.bot?.running
              ? `Automatic checks: ${state.bot.autoCalls}/10 · stops at ${time(state.bot.autoUntil)}`
              : "Automation is opt-in: one check per new completed minute, at most 10 checks or 10 minutes."
          }}
          Review only can explain saved data without creating an order.
        </p>
        <p v-if="replay" class="ai-notice">
          You are viewing recorded replay. Live trading controls are disabled
          here.
        </p>
        <div v-if="decision" class="ai-decision" aria-live="polite">
          <div class="ai-decision-top">
            <strong>{{
              decision.response.decision?.action.toUpperCase() ?? "NO ACTION"
            }}</strong
            ><span>{{ decision.status.toUpperCase() }}</span
            ><small>#{{ decision.id }} · {{ time(decision.createdAt) }}</small>
          </div>
          <p>
            {{ decision.response.decision?.reason ?? decision.response.reason }}
          </p>
          <p v-if="decision.status === 'review'" class="ai-caption">
            Review only. No simulated order was created.
          </p>
          <ul v-if="decision.response.checks?.length" class="ai-checks">
            <li
              v-for="c in decision.response.checks"
              :key="c.name"
              :class="{ failed: !c.passed }"
              :title="c.detail"
            >
              {{ c.passed ? "✓" : "×" }} {{ c.name }}
            </li>
          </ul>
          <details>
            <summary>Inspect the context and response</summary>
            <pre>{{ JSON.stringify(decision, null, 2) }}</pre>
          </details>
        </div>
        <div class="ai-account" aria-label="AI simulated account">
          <div>
            <small>Cash</small
            ><strong>{{ money(state?.bot?.account.cash ?? 10000) }}</strong>
          </div>
          <div>
            <small>Equity</small
            ><strong>{{ money(state?.bot?.account.equity ?? 10000) }}</strong>
          </div>
          <div>
            <small>Position</small
            ><strong>{{ state?.bot?.account.quantity ?? "0" }}</strong>
          </div>
          <div>
            <small>Realized P&amp;L</small
            ><strong>{{ money(state?.bot?.account.realizedPnl ?? 0) }}</strong>
          </div>
          <div>
            <small>Unrealized P&amp;L</small
            ><strong>{{
              money(state?.bot?.account.unrealizedPnl ?? 0)
            }}</strong>
          </div>
          <div>
            <small>Fees</small
            ><strong>{{ money(state?.bot?.account.fees ?? 0) }}</strong>
          </div>
        </div>
        <p class="ai-caption">
          Separate $10,000 AI account · buys use 95% of cash · 10 bps fee + 5
          bps slippage · fills use a later fresh Yahoo quote.
        </p>
        <div class="ai-orders">
          <h4>Actions and fills</h4>
          <p v-if="!state?.bot?.orders.length" class="ai-caption">
            No AI orders yet. Hold and rejected decisions leave the account
            unchanged.
          </p>
          <div
            v-for="order in [...(state?.bot?.orders ?? [])]
              .reverse()
              .slice(0, 5)"
            :key="order.id"
            class="ai-order"
          >
            <span
              >#{{ order.activityId }} · {{ order.side.toUpperCase()
              }}<small>{{ time(order.decisionTime) }}</small></span
            ><span
              >{{ order.status
              }}<small
                v-if="state?.bot?.fills.find((f) => f.orderId === order.id)"
                >{{
                  state.bot.fills.find((f) => f.orderId === order.id)?.quantity
                }}
                @
                {{
                  money(
                    state.bot.fills.find((f) => f.orderId === order.id)?.price,
                  )
                }}</small
              ></span
            >
          </div>
        </div>
      </div>
      <div class="ai-assistant">
        <div class="ai-tabs" role="tablist" aria-label="AI interaction">
          <button
            :class="{ active: activeTab === 'chat' }"
            role="tab"
            :aria-selected="activeTab === 'chat'"
            @click="activeTab = 'chat'"
          >
            <MessageCircle :size="17" />Chat</button
          ><button
            :class="{ active: activeTab === 'vision' }"
            role="tab"
            :aria-selected="activeTab === 'vision'"
            @click="activeTab = 'vision'"
          >
            <ScanLine :size="17" />Chart vision</button
          ><button
            :class="{ active: activeTab === 'voice' }"
            role="tab"
            :aria-selected="activeTab === 'voice'"
            @click="activeTab = 'voice'"
          >
            <Mic :size="17" />Live voice
          </button>
        </div>
        <div v-show="activeTab === 'chat'" class="ai-interaction">
          <h3>Ask about this workstation</h3>
          <p class="ai-caption">
            Receives recent Yahoo candles, completed-bar indicators, the AI
            account and its recent orders and fills. Replies explain data; they
            cannot submit trades.
          </p>
          <div class="ai-conversation" aria-live="polite">
            <p v-if="!conversations.length" class="ai-empty">
              Why did the bot hold? What changed in the account? Start with a
              question.
            </p>
            <article v-for="item in conversations" :key="item.id">
              <p class="ai-question">{{ item.response.question }}</p>
              <p>{{ item.response.text ?? item.response.reason }}</p>
              <small
                >{{ item.response.model ?? item.status }} · snapshot
                {{ time(item.createdAt) }}</small
              >
            </article>
          </div>
          <form @submit.prevent="ask()">
            <label for="ai-message">Your question</label
            ><textarea
              id="ai-message"
              v-model="message"
              maxlength="4000"
              rows="3"
              placeholder="Explain the current SMA candidate and simulated account."
            /><button
              class="ai-primary"
              :disabled="
                interactionBusy || !state?.configured || !message.trim()
              "
            >
              {{ interactionBusy ? "Asking the live model…" : "Ask assistant" }}
            </button>
          </form>
          <button
            class="ai-link"
            :disabled="interactionBusy || !state?.configured"
            @click="
              ask(
                'Explain the latest simulated account state and why the SMA candidate is buy, sell, or hold. State what remains uncertain.',
              )
            "
          >
            Explain this account
          </button>
        </div>
        <div v-show="activeTab === 'vision'" class="ai-interaction">
          <h3>Read the actual chart image</h3>
          <p class="ai-caption">
            Sends a PNG captured from the visible candlestick/SMA chart to
            {{ state?.visionModel ?? "Gemini Live" }}, alongside the server’s
            current data snapshot. Its spoken interpretation appears below as
            text. The image and exact values can differ slightly in time; visual
            interpretation cannot execute trades.
          </p>
          <button
            class="ai-primary"
            :disabled="interactionBusy || !state?.configured || replay"
            @click="analyze()"
          >
            <ScanLine :size="17" />{{
              interactionBusy ? "Interpreting image…" : "Analyze visible chart"
            }}</button
          ><img
            v-if="image"
            :src="image"
            alt="The actual chart image sent to the vision model"
            class="ai-chart-preview"
          />
          <article v-if="vision" class="ai-answer">
            <p>{{ vision.response.text ?? vision.response.reason }}</p>
            <small
              >{{ vision.response.model ?? vision.status }} ·
              {{ time(vision.createdAt) }}</small
            >
            <details>
              <summary>Inspect image fingerprint and context</summary>
              <pre>{{ JSON.stringify(vision, null, 2) }}</pre>
            </details>
          </article>
        </div>
        <div v-show="activeTab === 'voice'" class="ai-interaction">
          <h3>A live, two-way conversation</h3>
          <p class="ai-caption">
            {{ state?.audioModel ?? "Gemini Live" }} receives your microphone
            audio and a frozen workstation snapshot. It replies with streamed
            audio, not browser text-to-speech. Voice has no trading tools.
          </p>
          <div :class="['ai-voice-state', voiceState]">
            <Mic v-if="voiceState === 'live'" :size="24" /><MicOff
              v-else
              :size="24"
            /><strong>{{ voiceState.toUpperCase() }}</strong>
            <p role="status">{{ voiceDetail }}</p>
          </div>
          <div class="ai-actions">
            <button
              class="ai-primary"
              :disabled="
                !state?.configured ||
                voiceState === 'live' ||
                voiceState === 'connecting'
              "
              @click="startVoice()"
            >
              <Mic :size="17" />{{
                voiceState === "failed" ? "Reconnect voice" : "Start voice"
              }}</button
            ><button
              class="ai-secondary"
              :disabled="voiceState !== 'live' && voiceState !== 'connecting'"
              @click="voice?.stop()"
            >
              <MicOff :size="17" />End voice</button
            ><button
              v-if="state?.demoControls"
              class="ai-link"
              :disabled="voiceState !== 'live'"
              @click="voice?.injectFailure()"
            >
              Inject audio failure
            </button>
          </div>
          <audio
            ref="audio"
            autoplay
            controls
            aria-label="Live assistant audio"
          />
          <p class="ai-caption">
            {{
              voiceCapturedAt
                ? `Snapshot requested at ${time(voiceCapturedAt)}. `
                : ""
            }}Microphone stops on End, failure, symbol change, leaving this tab,
            or the two-minute limit. Reconnect for fresh context.
          </p>
          <div class="ai-transcripts" aria-live="polite">
            <p v-for="(line, index) in transcripts" :key="index">
              <strong>{{ line.role === "user" ? "You" : "Assistant" }}</strong>
              {{ line.text }}
            </p>
          </div>
          <details>
            <summary>Audio session evidence</summary>
            <p
              v-for="event in lastAudioEvents"
              :key="event.id"
              class="ai-caption"
            >
              {{ time(event.createdAt) }} · {{ event.status }} ·
              {{ event.response.evidence }} · {{ event.response.reason }}
            </p>
          </details>
        </div>
      </div>
    </div>
    <footer class="ai-footer">
      <ShieldCheck :size="16" />All trading is simulated. Model explanations can
      be wrong. Historical results and confidence do not predict future
      returns.<button class="ai-link" @click="refresh()">
        <RefreshCw :size="14" />Refresh context
      </button>
    </footer>
  </section>
</template>

<style scoped>
.ai-panel {
  margin: 28px 0;
  overflow: hidden;
}
.ai-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 30px;
  border-bottom: 1px solid var(--border);
}
h2 {
  font-size: 27px;
  margin: 8px 0;
}
h3 {
  font-size: 20px;
  margin: 0;
}
h4 {
  font-size: 16px;
  margin: 22px 0 10px;
}
.ai-heading p {
  color: #9eaf9e;
  margin: 0;
  line-height: 1.6;
}
.ai-provider,
.ai-pill {
  font-size: 13px;
  border: 1px solid #4b4e30;
  padding: 8px 12px;
  border-radius: 7px;
  color: #e0c58b;
  white-space: nowrap;
}
.ai-provider.ready {
  color: var(--green);
  border-color: #3b5231;
}
.ai-layout {
  display: grid;
  grid-template-columns: 1.1fr 1fr;
}
.ai-bot {
  padding: 28px 30px;
  border-right: 1px solid var(--border);
}
.ai-title {
  display: flex;
  gap: 10px;
  align-items: center;
}
.ai-title > svg {
  color: var(--green);
}
.ai-pill {
  margin-left: auto;
  color: var(--green);
  font-size: 12px;
}
.ai-caption {
  font-size: 14px;
  line-height: 1.65;
  color: #9aaa97;
}
.ai-signal {
  display: grid;
  grid-template-columns: 1fr 1.4fr 0.7fr;
  gap: 14px;
  background: #172017;
  padding: 18px;
  border-radius: 8px;
  margin: 18px 0;
}
.ai-signal small,
.ai-account small {
  display: block;
  color: #9aaa97;
  font-size: 13px;
  margin-bottom: 7px;
}
.ai-signal strong {
  font-size: 15px;
}
.ai-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.ai-primary,
.ai-secondary {
  font-size: 14px;
  padding: 12px 15px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.ai-primary {
  background: var(--green);
  color: #162010;
  font-weight: 650;
}
.ai-secondary {
  background: #202b20;
  border: 1px solid #43553a;
  color: var(--green);
}
.ai-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  color: var(--green);
  font-size: 14px;
  padding: 8px 2px;
  text-decoration: underline;
  text-underline-offset: 4px;
}
.ai-decision {
  padding: 20px;
  background: #172016;
  border: 1px solid #3e5234;
  border-radius: 8px;
  margin: 20px 0;
}
.ai-decision-top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.ai-decision-top strong {
  font-size: 21px;
  color: var(--green);
}
.ai-decision-top span {
  font-size: 12px;
  letter-spacing: 0.06em;
}
.ai-decision-top small {
  font-size: 12px;
  color: #9aaa97;
}
.ai-decision p,
.ai-answer p,
.ai-conversation p {
  font-size: 15px;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.ai-checks {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  list-style: none;
  padding: 0;
}
.ai-checks li {
  font-size: 13px;
  color: #bde693;
}
.ai-checks li.failed {
  color: #eda88a;
}
.ai-account {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px 14px;
  padding: 22px 0;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}
.ai-account strong {
  font-size: 18px;
  overflow-wrap: anywhere;
  font-variant-numeric: tabular-nums;
}
.ai-order {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 13px 0;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
}
.ai-order small {
  display: block;
  font-size: 12px;
  color: #9aaa97;
  margin-top: 5px;
}
.ai-order > span:last-child {
  text-align: right;
}
.ai-tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  padding: 0 18px;
}
.ai-tabs button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  flex: 1;
  background: transparent;
  color: #a6b49e;
  padding: 24px 10px;
  font-size: 14px;
  border-bottom: 3px solid transparent;
}
.ai-tabs button.active {
  color: var(--green);
  border-bottom-color: var(--green);
}
.ai-interaction {
  padding: 28px;
}
.ai-conversation {
  max-height: 430px;
  overflow: auto;
  margin: 20px 0;
  min-height: 130px;
}
.ai-empty {
  color: #899b87;
  padding: 20px;
  border: 1px dashed #344431;
  border-radius: 8px;
}
.ai-conversation article {
  border-bottom: 1px solid var(--border);
  padding: 4px 0 18px;
}
.ai-question {
  background: #263622;
  padding: 12px 16px;
  border-radius: 6px;
}
.ai-conversation small,
.ai-answer small {
  font-size: 12px;
  color: #91a386;
}
form label {
  font-size: 14px;
  display: block;
  margin: 12px 0 8px;
}
textarea {
  width: 100%;
  resize: vertical;
  background: #0d140e;
  color: #e4eadf;
  border: 1px solid #3d5035;
  border-radius: 6px;
  font: inherit;
  font-size: 15px;
  line-height: 1.6;
  padding: 12px;
  margin-bottom: 12px;
}
.ai-chart-preview {
  display: block;
  width: 100%;
  margin-top: 20px;
  border: 1px solid var(--border);
  border-radius: 7px;
}
.ai-answer {
  padding-top: 10px;
}
.ai-voice-state {
  padding: 24px;
  margin: 20px 0;
  text-align: center;
  background: #152016;
  border: 1px solid #354c32;
  border-radius: 8px;
}
.ai-voice-state svg {
  vertical-align: middle;
  margin-right: 10px;
}
.ai-voice-state.live {
  border-color: var(--green);
  color: var(--green);
}
.ai-voice-state.failed {
  border-color: #b17d60;
  color: #eeb68f;
}
.ai-voice-state p {
  font-size: 14px;
  line-height: 1.6;
}
audio {
  width: 100%;
  height: 42px;
  margin: 22px 0 4px;
}
.ai-transcripts {
  max-height: 270px;
  overflow: auto;
  font-size: 15px;
  line-height: 1.6;
}
.ai-transcripts strong {
  color: var(--green);
  margin-right: 7px;
}
.ai-footer {
  border-top: 1px solid var(--border);
  padding: 18px 28px;
  font-size: 13px;
  color: #a1b298;
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.ai-footer .ai-link {
  margin-left: auto;
}
.ai-notice,
.ai-error {
  font-size: 14px;
  line-height: 1.6;
  margin: 18px 28px;
  padding: 14px 18px;
  border-radius: 6px;
  background: #292719;
  color: #dfcf98;
}
.ai-error {
  background: #34221b;
  color: #f2b799;
}
.ai-bot .ai-notice {
  margin: 12px 0;
}
details {
  margin-top: 15px;
  font-size: 13px;
  color: #a4b79b;
}
summary {
  cursor: pointer;
  padding: 5px 0;
}
pre {
  font-size: 12px;
  line-height: 1.5;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: #0b120c;
  padding: 12px;
  border-radius: 6px;
}
@media (max-width: 1050px) {
  .ai-layout {
    grid-template-columns: 1fr;
  }
  .ai-bot {
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }
  .ai-assistant {
    min-height: 430px;
  }
}
@media (max-width: 640px) {
  .ai-heading {
    align-items: flex-start;
    flex-direction: column;
    padding: 22px;
  }
  .ai-bot,
  .ai-interaction {
    padding: 22px;
  }
  .ai-signal {
    grid-template-columns: 1fr 1fr;
  }
  .ai-account {
    grid-template-columns: 1fr 1fr;
  }
  .ai-title h3 {
    font-size: 18px;
  }
  .ai-tabs {
    padding: 0 8px;
  }
  .ai-tabs button {
    padding: 20px 7px;
    font-size: 13px;
  }
}
</style>
