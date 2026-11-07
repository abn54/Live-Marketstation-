import WebSocket from "ws";
import protobuf from "protobufjs";
import { fileURLToPath } from "node:url";
const PricingData = protobuf
  .loadSync(fileURLToPath(new URL("./pricing.proto", import.meta.url)))
  .lookupType("PricingData");
export const SYMBOLS = ["BTC-USD", "ETH-USD", "SPY", "AAPL"];

export function decodeQuote(raw, receivedAt = Date.now()) {
  const envelope = JSON.parse(raw.toString());
  if (envelope.type !== "pricing" || typeof envelope.message !== "string")
    return null;
  const p = PricingData.toObject(
    PricingData.decode(Buffer.from(envelope.message, "base64")),
    { longs: Number, defaults: false },
  );
  if (
    !SYMBOLS.includes(p.id) ||
    !Number.isFinite(p.price) ||
    !Number.isSafeInteger(p.time)
  )
    throw new Error("Malformed Yahoo quote");
  return {
    source: "yahoo-stream",
    kind: "quote",
    symbol: p.id,
    interval: "tick",
    sourceTime: p.time,
    receivedAt,
    orderingTime: receivedAt,
    payload: {
      price: p.price,
      currency: p.currency ?? "USD",
      dayVolume: p.dayVolume ?? null,
      changePercent: p.changePercent ?? null,
      exchange: p.exchange ?? null,
      marketHours: p.marketHours ?? null,
    },
  };
}

export function normalizeChart(data, symbol, requestStartedAt, receivedAt) {
  const result = data?.chart?.result?.[0];
  if (
    data?.chart?.error ||
    !result?.timestamp?.length ||
    !result.indicators?.quote?.[0]
  )
    throw new Error(
      data?.chart?.error?.description ?? "Yahoo returned no candle data",
    );
  const q = result.indicators.quote[0],
    bars = new Map();
  const maxBucket = Math.floor(Math.max(...result.timestamp) / 60) * 60000;
  result.timestamp.forEach((t, i) => {
    const sourceTime = Math.floor(t / 60) * 60000;
    const values = [q.open?.[i], q.high?.[i], q.low?.[i], q.close?.[i]];
    if (!values.every((v) => Number.isFinite(v) && v > 0)) return;
    // Yahoo sometimes appends an unaligned last-price row to an existing minute.
    // Prefer the actual OHLCV row rather than replacing its volume with zero.
    if (bars.has(sourceTime) && t % 60 !== 0) return;
    bars.set(sourceTime, {
      source: "yahoo-chart",
      kind: "candle",
      symbol,
      interval: "1m",
      sourceTime,
      receivedAt,
      orderingTime: requestStartedAt,
      payload: {
        open: values[0],
        high: values[1],
        low: values[2],
        close: values[3],
        volume:
          Number.isFinite(q.volume?.[i]) && q.volume[i] >= 0
            ? q.volume[i]
            : null,
        complete:
          sourceTime < maxBucket && sourceTime + 60000 <= requestStartedAt,
      },
    });
  });
  if (!bars.size) throw new Error("Yahoo returned no valid candles");
  return {
    observations: [...bars.values()].sort(
      (a, b) => a.sourceTime - b.sourceTime,
    ),
    meta: {
      name: result.meta?.shortName ?? symbol,
      currency: result.meta?.currency ?? "USD",
      exchange: result.meta?.exchangeName ?? "Unknown",
      marketTime: result.meta?.regularMarketTime * 1000 || null,
    },
  };
}

export class YahooFeed {
  constructor({
    store,
    onData,
    onStatus,
    pollMs = 15000,
    fetchImpl = fetch,
    now = Date.now,
    webSocketFactory = (url) =>
      new WebSocket(url, {
        headers: {
          "User-Agent": "Mozilla/5.0",
          Origin: "https://finance.yahoo.com",
        },
        handshakeTimeout: 10000,
      }),
  }) {
    Object.assign(this, {
      store,
      onData,
      onStatus,
      pollMs,
      fetchImpl,
      now,
      webSocketFactory,
    });
    this.stopped = true;
    this.paused = false;
    this.attempt = 0;
    this.states = {
      stream: { state: "connecting", detail: "Waiting for Yahoo WebSocket" },
      chart: { state: "connecting", detail: "Waiting for Yahoo candles" },
    };
    this.symbols = {};
    this.controllers = new Set();
    this.generation = 0;
  }
  status() {
    return {
      ...this.states,
      paused: this.paused,
      symbols: this.symbols,
      pollMs: this.pollMs,
    };
  }
  setStatus(channel, state, detail, extra = {}) {
    const previous = this.states[channel];
    this.states[channel] = { ...previous, ...extra, state, detail };
    if (previous.state !== state || previous.detail !== detail)
      this.store.event(channel, state, detail, this.now());
    this.onStatus?.(this.status());
  }
  start() {
    this.stopped = false;
    this.connect();
    this.poll();
    this.pollTimer = setInterval(() => this.poll(), this.pollMs);
  }
  connect() {
    if (this.stopped || this.paused) return;
    this.setStatus("stream", "connecting", "Connecting to Yahoo Finance");
    const ws = this.webSocketFactory(
      "wss://streamer.finance.yahoo.com/?version=2",
    );
    this.ws = ws;
    ws.on("open", () => {
      if (this.stopped || this.paused || ws !== this.ws) return ws.close();
      this.attempt = 0;
      this.setStatus(
        "stream",
        "connected",
        "Connected; waiting for a pricing message",
      );
      const subscribe = () => {
        if (ws.readyState === WebSocket.OPEN)
          ws.send(JSON.stringify({ subscribe: SYMBOLS }));
      };
      subscribe();
      this.subscriptionTimer = setInterval(subscribe, 15000);
    });
    ws.on("message", (raw) => {
      if (this.stopped || this.paused || ws !== this.ws) return;
      try {
        const o = decodeQuote(raw, this.now());
        if (!o) return;
        const results = this.store.ingestBatch([o]);
        this.symbols[o.symbol] = {
          ...this.symbols[o.symbol],
          lastQuoteReceivedAt: o.receivedAt,
          lastQuoteSourceTime: o.sourceTime,
        };
        this.setStatus(
          "stream",
          "streaming",
          "Receiving Yahoo pricing messages",
          { lastReceivedAt: o.receivedAt },
        );
        this.onData?.(results);
      } catch (e) {
        this.setStatus("stream", "degraded", `Quote rejected: ${e.message}`);
      }
    });
    ws.on("error", (e) => {
      if (ws === this.ws && !this.paused && !this.stopped)
        this.setStatus(
          "stream",
          "unavailable",
          `Yahoo WebSocket: ${e.message}`,
        );
    });
    ws.on("close", () => {
      if (this.stopped || this.paused || ws !== this.ws) return;
      clearInterval(this.subscriptionTimer);
      const delay = Math.min(30000, 1000 * 2 ** this.attempt++);
      this.setStatus(
        "stream",
        "unavailable",
        `Yahoo disconnected; retry in ${delay / 1000}s`,
      );
      this.reconnectTimer = setTimeout(() => this.connect(), delay);
    });
  }
  async fetchSymbol(symbol) {
    const started = this.now(),
      generation = this.generation;
    const controller = new AbortController();
    this.controllers.add(controller);
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const latest = this.store.candles(symbol, 1).at(-1);
      const query = latest
        ? `interval=1m&period1=${Math.floor(latest.sourceTime / 1000) - 180}&period2=${Math.floor(started / 1000) + 60}`
        : "interval=1m&range=1d";
      const response = await this.fetchImpl(
        `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?${query}`,
        {
          headers: { "User-Agent": "Mozilla/5.0", Accept: "application/json" },
          signal: controller.signal,
        },
      );
      if (!response.ok) throw new Error(`Yahoo HTTP ${response.status}`);
      const data = await response.json();
      if (this.paused || this.stopped || generation !== this.generation) return;
      const received = this.now(),
        normalized = normalizeChart(data, symbol, started, received);
      const results = this.store.ingestBatch(normalized.observations);
      this.symbols[symbol] = {
        ...this.symbols[symbol],
        ...normalized.meta,
        chartState: "available",
        chartError: null,
        lastChartReceivedAt: received,
        lastCandleSourceTime: normalized.observations.at(-1).sourceTime,
      };
      // Commit before publishing: every observation sent to a browser is queryable.
      this.onData?.(results);
    } catch (e) {
      if (this.paused || this.stopped || generation !== this.generation) return;
      this.symbols[symbol] = {
        ...this.symbols[symbol],
        chartState: "unavailable",
        chartError:
          e.name === "AbortError" ? "Yahoo chart request timed out" : e.message,
      };
    } finally {
      clearTimeout(timeout);
      this.controllers.delete(controller);
    }
  }
  async poll() {
    if (this.polling || this.paused || this.stopped) return;
    this.polling = true;
    try {
      // Serial requests avoid burst traffic and overlapping cycles.
      for (const symbol of SYMBOLS) {
        if (this.paused || this.stopped) break;
        await this.fetchSymbol(symbol);
      }
      if (this.paused || this.stopped) return;
      const available = SYMBOLS.filter(
        (s) => this.symbols[s]?.chartState === "available",
      ).length;
      this.setStatus(
        "chart",
        available === SYMBOLS.length
          ? "available"
          : available
            ? "degraded"
            : "unavailable",
        `${available}/${SYMBOLS.length} candle sources available`,
        { lastReceivedAt: this.now() },
      );
    } finally {
      this.polling = false;
    }
  }
  pause() {
    if (this.paused) return;
    this.paused = true;
    this.generation++;
    for (const symbol of SYMBOLS)
      this.symbols[symbol] = {
        ...this.symbols[symbol],
        chartState: "unavailable",
        chartError: "Upstream intentionally disconnected for demonstration",
      };
    clearTimeout(this.reconnectTimer);
    clearInterval(this.subscriptionTimer);
    this.ws?.terminate();
    this.controllers.forEach((c) => c.abort());
    for (const channel of ["stream", "chart"])
      this.setStatus(
        channel,
        "unavailable",
        "Demonstration: upstream connections intentionally disconnected",
      );
  }
  resume() {
    if (!this.paused) return;
    this.paused = false;
    this.connect();
    this.poll();
  }
  stop() {
    this.stopped = true;
    this.generation++;
    clearInterval(this.pollTimer);
    clearInterval(this.subscriptionTimer);
    clearTimeout(this.reconnectTimer);
    this.controllers.forEach((c) => c.abort());
    this.ws?.terminate();
  }
}
