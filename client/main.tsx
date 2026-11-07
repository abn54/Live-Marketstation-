import React, { useEffect, useRef, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import {
  Activity,
  ArrowDownLeft,
  ArrowUpRight,
  ChartCandlestick,
  ChevronDown,
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
  WifiOff,
} from "lucide-react";
import { MarketChart } from "./Chart";
import type {
  Feed,
  Observation,
  Receipt,
  ReplayRecord,
  Stats,
  SymbolData,
} from "./types";
import "./styles.css";
const symbols = ["BTC-USD", "ETH-USD", "SPY", "AAPL"];
const names: Record<string, string> = {
  "BTC-USD": "Bitcoin",
  "ETH-USD": "Ethereum",
  SPY: "S&P 500 ETF",
  AAPL: "Apple Inc.",
};
const initialFeed: Feed = {
  stream: { state: "connecting", detail: "Connecting to server" },
  chart: { state: "connecting", detail: "Waiting for candles" },
  paused: false,
  pollMs: 15000,
  symbols: {},
};
const emptyStats: Stats = {
  observations: 0,
  revisions: 0,
  receipts: 0,
  duplicates: 0,
  superseded: 0,
  candles: 0,
  lastReceiptId: 0,
  journalMode: "wal",
};
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
const age = (v: number | undefined, now: number) =>
  !v
    ? "No observation"
    : Math.max(0, Math.floor((now - v) / 1000)) < 60
      ? `${Math.max(0, Math.floor((now - v) / 1000))}s ago`
      : `${Math.floor((now - v) / 60000)}m ago`;
function merge(a: Observation[], o: Observation) {
  const next = [...a.filter((x) => x.logicalId !== o.logicalId), o].sort(
    (x, y) => x.sourceTime - y.sourceTime,
  );
  return next.slice(-360);
}
function apply(old: SymbolData, o: Observation): SymbolData {
  return o.kind === "candle"
    ? { ...old, candles: merge(old.candles, o) }
    : !old.quote || o.sourceTime >= old.quote.sourceTime
      ? { ...old, quote: o }
      : old;
}
const blank = (symbol: string): SymbolData => ({
  symbol,
  candles: [],
  quote: null,
  receipts: [],
});

function App() {
  const [data, setData] = useState<Record<string, SymbolData>>({}),
    [selected, setSelected] = useState("BTC-USD"),
    [feed, setFeed] = useState(initialFeed),
    [stats, setStats] = useState(emptyStats),
    [connected, setConnected] = useState(false),
    [now, setNow] = useState(Date.now()),
    [demo, setDemo] = useState(false),
    [mode, setMode] = useState<"live" | "replay">("live"),
    [fitKey, setFitKey] = useState(0),
    [help, setHelp] = useState(false),
    [tab, setTab] = useState<"observations" | "pipeline">("observations"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [records, setRecords] = useState<ReplayRecord[]>([]),
    [cursor, setCursor] = useState(0),
    [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(4),
    [replayData, setReplayData] = useState<SymbolData>(blank("BTC-USD"));
  const replayGeneration = useRef(0);
  useEffect(() => {
    let disposed = false,
      ws: WebSocket,
      timer: ReturnType<typeof setTimeout>;
    function connect() {
      ws = new WebSocket(
        `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws`,
      );
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!disposed) timer = setTimeout(connect, 1500);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (e) => {
        const m = JSON.parse(e.data);
        if (m.status) setFeed(m.status);
        if (m.stats) setStats(m.stats);
        if (m.type === "snapshot") {
          setDemo(m.demoControls);
          setData(
            Object.fromEntries(m.symbols.map((s: SymbolData) => [s.symbol, s])),
          );
        }
        if (m.type === "observations")
          setData((old) => {
            const next = { ...old };
            for (const r of m.results) {
              const o = r.observation;
              if (r.applied)
                next[o.symbol] = apply(next[o.symbol] ?? blank(o.symbol), o);
              const s = next[o.symbol] ?? blank(o.symbol);
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
            return next;
          });
      };
    }
    connect();
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      disposed = true;
      clearTimeout(timer);
      clearInterval(tick);
      ws?.close();
    };
  }, []);
  // Read receipt history after bootstrap and symbol changes (including duplicate receipts).
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/receipts?symbol=${selected}`, { signal: controller.signal })
      .then((r) => r.json())
      .then((d) =>
        setData((old) => ({
          ...old,
          [selected]: {
            ...(old[selected] ?? blank(selected)),
            receipts: d.receipts,
          },
        })),
      )
      .catch(() => {});
    return () => controller.abort();
  }, [selected]);
  useEffect(() => {
    if (!playing || mode !== "replay") return;
    const t = setInterval(
      () => setCursor((v) => Math.min(v + 1, records.length)),
      1000 / speed,
    );
    return () => clearInterval(t);
  }, [playing, speed, mode, records.length]);
  useEffect(() => {
    let s = blank(selected);
    for (const r of records.slice(0, cursor)) {
      if (r.applied) s = apply(s, r.observation);
      s.receipts = [
        {
          ...r.observation,
          receiptId: r.receiptId,
          disposition: r.disposition,
          receiptTime: r.receivedAt,
        },
        ...s.receipts,
      ].slice(0, 12);
    }
    setReplayData(s);
    if (cursor >= records.length) setPlaying(false);
  }, [cursor, records, selected]);
  const live = data[selected] ?? blank(selected),
    shown = mode === "replay" ? replayData : live,
    last = shown.candles.at(-1),
    quote = shown.quote,
    price = quote?.price ?? last?.close,
    first = shown.candles[0],
    change =
      quote?.changePercent ??
      (first && price ? (price / first.open! - 1) * 100 : 0),
    meta = feed.symbols[selected];
  const quoteStale = !live.quote || now - live.quote.sourceTime > 60000,
    candleStale =
      !live.candles.at(-1) || now - live.candles.at(-1)!.sourceTime > 180000;
  const feedUnavailable =
    feed.paused ||
    meta?.chartState === "unavailable" ||
    feed.stream.state === "unavailable";
  const statusLabel =
    mode === "replay"
      ? "RECORDED REPLAY"
      : !connected
        ? "SERVER OFFLINE"
        : feedUnavailable
          ? "FEED UNAVAILABLE"
          : quoteStale || candleStale
            ? "WAITING / STALE"
            : "LIVE FEED";
  const collectorGood =
    connected && !feedUnavailable && !quoteStale && !candleStale;
  const good = mode === "live" && collectorGood;
  async function startReplay() {
    setBusy(true);
    setError("");
    setPlaying(false);
    const generation = ++replayGeneration.current;
    const symbol = selected;
    try {
      let after = 0,
        until: number | undefined,
        all: ReplayRecord[] = [];
      for (let page = 0; page < 100; page++) {
        const r = await fetch(
          `/api/replay?symbol=${symbol}&after=${after}&limit=2000${until === undefined ? "" : `&until=${until}`}`,
        );
        if (!r.ok) throw new Error("Replay could not be loaded");
        const d = await r.json();
        until = d.until;
        all.push(...d.records);
        after = d.nextAfter;
        if (d.done) break;
        if (page === 99)
          throw new Error(
            "Recording exceeds browser replay limit; use paginated API",
          );
      }
      if (generation !== replayGeneration.current) return;
      if (!all.length)
        throw new Error("No recorded observations for this symbol yet");
      // Start at the final 80 receipts with the preceding state reconstructed, so
      // startup history is visible and playback quickly shows real revisions.
      setRecords(all);
      setCursor(Math.max(0, all.length - 80));
      setMode("replay");
      setPlaying(true);
      setFitKey((k) => k + 1);
    } catch (e) {
      if (generation === replayGeneration.current)
        setError((e as Error).message);
    } finally {
      if (generation === replayGeneration.current) setBusy(false);
    }
  }
  async function toggleFeed() {
    setBusy(true);
    setError("");
    try {
      const r = await fetch("/api/demo/feed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: feed.paused ? "reconnect" : "disconnect",
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error);
      setFeed(d.feed);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function choose(symbol: string) {
    setSelected(symbol);
    setMode("live");
    setPlaying(false);
    setRecords([]);
    setCursor(0);
    setError("");
    replayGeneration.current++;
    setBusy(false);
  }
  return (
    <div className="shell">
      <aside className="rail">
        <a className="brandmark" href="/" aria-label="Marketstation home">
          <Activity size={24} />
        </a>
        <div className="rail-line" />
        <button
          className="rail-button active"
          title="Market dashboard"
          aria-label="Market dashboard"
          onClick={() => {
            setMode("live");
            setTab("observations");
          }}
        >
          <ChartCandlestick size={21} />
        </button>
        <button
          className="rail-button"
          title="Recorded replay"
          aria-label="Recorded replay"
          onClick={startReplay}
        >
          <FileClock size={21} />
        </button>
        <button
          className="rail-button"
          title="Data pipeline"
          aria-label="Data pipeline"
          onClick={() => setTab("pipeline")}
        >
          <Database size={21} />
        </button>
        <div className="rail-bottom">
          <button
            className="rail-button"
            aria-label="About this workstation"
            onClick={() => setHelp(!help)}
          >
            <CircleHelp size={20} />
          </button>
          <div className="avatar">AN</div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="wordmark">
            marketstation<span className="brand-dot">.</span>
            <span className="edition">WORKSTATION / 01</span>
          </div>
          <div className="top-right">
            <span className="desktop-clock">{time(now)}</span>
            <span className={`connection ${connected ? "" : "bad"}`}>
              <span className="dot" />
              {connected ? "Server connected" : "Reconnecting to server"}
            </span>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">THE MARKET, IN MOTION</div>
              <h1>
                Market overview<span className="heading-dot">.</span>
              </h1>
              <p>A live view. A lasting record.</p>
            </div>
            <div className="heading-actions">
              <span
                className={`status-pill ${good ? "good" : mode === "replay" ? "replay" : "warning"}`}
              >
                <span className="dot" />
                {statusLabel}
              </span>
              <span className="source-tag">
                <Globe2 size={13} />
                Yahoo Finance
              </span>
            </div>
          </div>
          {help && (
            <div className="notice">
              Part 4.1 · Yahoo quotes stream over WebSockets; one-minute OHLCV
              is fetched every {feed.pollMs / 1000}s and streamed from the
              server after a SQLite commit. Candle times are UTC. Yahoo data can
              be delayed or unavailable. Replay uses persisted receipts and
              never writes them back.
            </div>
          )}
          {error && (
            <div className="notice warning" role="alert">
              {error}
            </div>
          )}
          <div className="watchlist">
            {symbols.map((s) => {
              const d = data[s],
                q = d?.quote,
                c = d?.candles.at(-1),
                pct = q?.changePercent;
              return (
                <button
                  className={`watch-card ${selected === s ? "selected" : ""}`}
                  key={s}
                  onClick={() => choose(s)}
                >
                  <span
                    className={`coin-icon ${s === "ETH-USD" ? "eth" : s === "SPY" ? "spy" : s === "AAPL" ? "apple" : ""}`}
                  >
                    {s === "BTC-USD"
                      ? "₿"
                      : s === "ETH-USD"
                        ? "Ξ"
                        : s === "SPY"
                          ? "S"
                          : "A"}
                  </span>
                  <span className="watch-name">
                    <strong>{s}</strong>
                    <small>{names[s]}</small>
                  </span>
                  <span className="watch-values">
                    <strong>${money(q?.price ?? c?.close)}</strong>
                    <small
                      className={(pct ?? 0) >= 0 ? "positive" : "negative"}
                    >
                      {pct === null || pct === undefined
                        ? "Recorded candles"
                        : `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`}
                    </small>
                  </span>
                  {selected === s && <span className="selected-indicator" />}
                </button>
              );
            })}
          </div>
          <div className="dashboard-grid">
            <section className="panel chart-panel">
              <div className="instrument-header">
                <div className="instrument-title">
                  <h2>
                    {names[selected]}
                    <span>/ USD</span>
                  </h2>
                  <span className="asset-label">
                    {selected.includes("USD") ? "CRYPTO" : "EQUITY"}
                    <span>•</span>
                    {meta?.exchange ?? "Yahoo Finance"}
                  </span>
                </div>
                <div className="mode-toggle">
                  <button
                    className={mode === "live" ? "on" : ""}
                    onClick={() => {
                      setMode("live");
                      setPlaying(false);
                    }}
                  >
                    <Radio size={13} />
                    Live
                  </button>
                  <button
                    className={mode === "replay" ? "on" : ""}
                    disabled={busy}
                    onClick={startReplay}
                  >
                    <FileClock size={13} />
                    Replay
                  </button>
                </div>
              </div>
              <div className="price-row">
                <strong className="big-price">${money(price)}</strong>
                <span
                  className={`price-change ${change >= 0 ? "positive" : "negative"}`}
                >
                  {change >= 0 ? (
                    <ArrowUpRight size={16} />
                  ) : (
                    <ArrowDownLeft size={16} />
                  )}{" "}
                  {change >= 0 ? "+" : ""}
                  {change.toFixed(2)}%
                  <small>{quote ? "Yahoo change" : "visible window"}</small>
                </span>
                <span className="price-time">
                  {mode === "replay"
                    ? "Recorded source time"
                    : "Quote source time"}
                  <b>{time(quote?.sourceTime ?? last?.sourceTime)}</b>
                </span>
              </div>
              <div className="chart-toolbar">
                <div className="interval-selector">
                  <span className="interval-active">1m</span>
                  <span>ONE-MINUTE CANDLES</span>
                </div>
                <div className="chart-legend">
                  <span>
                    <i className="legend-line" />
                    Price
                  </span>
                  <span>
                    <i className="legend-bar" />
                    Volume
                  </span>
                  <button
                    onClick={() => setFitKey((v) => v + 1)}
                    aria-label="Fit chart to data"
                    title="Fit chart"
                  >
                    <Expand size={15} />
                  </button>
                </div>
              </div>
              <div className="ohlc-strip">
                {[
                  ["O", last?.open],
                  ["H", last?.high],
                  ["L", last?.low],
                  ["C", last?.close],
                ].map(([k, v]) => (
                  <span key={k}>
                    <small>{k}</small>
                    {money(v as number | undefined)}
                  </span>
                ))}
                <span className="candle-state">
                  <span
                    className={`dot ${last?.complete ? "muted-dot" : ""}`}
                  />
                  {last
                    ? last.complete
                      ? "Complete candle"
                      : "Forming candle"
                    : "Awaiting candles"}
                </span>
              </div>
              <div className="chart-wrap">
                <MarketChart
                  candles={shown.candles}
                  symbol={`${selected}:${mode}`}
                  fitKey={fitKey}
                />
                {!shown.candles.length && (
                  <div className="chart-empty">
                    <ChartCandlestick size={28} />
                    <strong>
                      {mode === "replay"
                        ? "Recorded playback ready"
                        : "Waiting for Yahoo candles"}
                    </strong>
                    <span>
                      {meta?.chartError ??
                        "Observations appear here after they are committed to SQLite."}
                    </span>
                  </div>
                )}
                {mode === "replay" && (
                  <div className="replay-watermark">RECORDED</div>
                )}
              </div>
              <div className="chart-footer">
                <span>
                  <span className={`dot ${good ? "" : "muted-dot"}`} />
                  {mode === "replay"
                    ? "SQLite recording"
                    : feedUnavailable
                      ? "Upstream unavailable · retained data"
                      : `Yahoo Chart · ${feed.pollMs / 1000}s refresh`}
                  <b>OHLCV</b>
                </span>
                <span>
                  Vol{" "}
                  {last?.volume === null || last?.volume === undefined
                    ? "unreported"
                    : count(last.volume)}{" "}
                  · UTC
                </span>
              </div>
              {mode === "replay" && (
                <div className="replay-controls">
                  <button
                    aria-label={playing ? "Pause replay" : "Play replay"}
                    onClick={() => {
                      if (cursor >= records.length) setCursor(0);
                      setPlaying(!playing);
                    }}
                  >
                    {playing ? <Pause size={16} /> : <Play size={16} />}
                  </button>
                  <button
                    aria-label="Restart replay"
                    onClick={() => {
                      setCursor(0);
                      setPlaying(true);
                    }}
                  >
                    <RotateCcw size={15} />
                  </button>
                  <input
                    aria-label="Replay position"
                    type="range"
                    min={0}
                    max={records.length}
                    value={cursor}
                    onChange={(e) => {
                      setPlaying(false);
                      setCursor(Number(e.target.value));
                    }}
                  />
                  <span>
                    {cursor} / {records.length}
                  </span>
                  <select
                    aria-label="Replay speed"
                    value={speed}
                    onChange={(e) => setSpeed(Number(e.target.value))}
                  >
                    <option value={1}>1 receipt/s</option>
                    <option value={4}>4 receipts/s</option>
                    <option value={20}>20 receipts/s</option>
                    <option value={100}>100 receipts/s</option>
                  </select>
                </div>
              )}
            </section>
            <aside className="right-stack">
              <section className="panel feed-panel">
                <div className="panel-heading">
                  <h3>
                    <Radio size={15} />
                    Feed health
                  </h3>
                  <span className="tiny-tag">LIVE SOURCE</span>
                </div>
                <div className={`feed-health ${collectorGood ? "" : "amber"}`}>
                  <span className="pulse-dot" />
                  <div>
                    <strong>
                      {feed.paused
                        ? "Upstream disconnected"
                        : !connected
                          ? "Server disconnected"
                          : collectorGood
                            ? "Receiving market data"
                            : feedUnavailable
                              ? "Feed needs attention"
                              : "Waiting for fresh data"}
                    </strong>
                    <small>
                      {feed.paused
                        ? "Intentional outage demonstration"
                        : mode === "replay"
                          ? "Live collection continues during replay"
                          : feed.stream.detail}
                    </small>
                  </div>
                </div>
                <dl className="key-values">
                  <div>
                    <dt>Provider</dt>
                    <dd>
                      Yahoo Finance
                      <ArrowUpRight size={11} />
                    </dd>
                  </div>
                  <div>
                    <dt>Quote age</dt>
                    <dd className={quoteStale ? "amber" : ""}>
                      {age(live.quote?.sourceTime, now)}
                    </dd>
                  </div>
                  <div>
                    <dt>Candle age</dt>
                    <dd className={candleStale ? "amber" : ""}>
                      {age(live.candles.at(-1)?.sourceTime, now)}
                    </dd>
                  </div>
                  <div>
                    <dt>Last receipt</dt>
                    <dd>
                      {age(
                        Math.max(
                          meta?.lastQuoteReceivedAt ?? 0,
                          meta?.lastChartReceivedAt ?? 0,
                        ) || undefined,
                        now,
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>Yahoo socket</dt>
                    <dd
                      className={
                        feed.stream.state === "streaming" ? "positive" : "amber"
                      }
                    >
                      {feed.stream.state}
                    </dd>
                  </div>
                  <div>
                    <dt>Candle endpoint</dt>
                    <dd
                      className={
                        meta?.chartState === "available" ? "positive" : "amber"
                      }
                    >
                      {meta?.chartState ?? "connecting"}
                    </dd>
                  </div>
                </dl>
                {meta?.chartError && (
                  <div className="inline-error">{meta.chartError}</div>
                )}
                <div className="health-note">
                  <ShieldCheck size={14} />
                  <span>Source time and receipt time tracked separately.</span>
                </div>
              </section>
              <section className="panel storage-panel">
                <div className="panel-heading">
                  <h3>
                    <Database size={15} />
                    Persistent by design
                  </h3>
                  <span className="sqlite-tag">SQLite</span>
                </div>
                <div className="record-count">
                  {count(stats.observations)}
                  <span>stored observations</span>
                </div>
                <div className="storage-grid">
                  <div>
                    <b>{count(stats.revisions)}</b>
                    <span>revisions</span>
                  </div>
                  <div>
                    <b>{count(stats.duplicates)}</b>
                    <span>duplicates</span>
                  </div>
                  <div>
                    <b>{count(stats.candles)}</b>
                    <span>candles</span>
                  </div>
                </div>
                <div className="commit-line">
                  <span className="dot" />
                  Committed before broadcast<span className="wal-tag">WAL</span>
                </div>
                <button
                  className="full-button"
                  onClick={startReplay}
                  disabled={busy}
                >
                  <FileClock size={14} />
                  {busy ? "Loading…" : "Explore recorded data"}
                  <ChevronRight size={15} />
                </button>
              </section>
              <section className="session-note">
                <span className="eyebrow">BUILT TO BE TRACEABLE</span>
                <p>
                  Every update has a source.
                  <br />
                  Every revision leaves a record.
                </p>
                <div>
                  <Layers3 size={14} />
                  Part 4.1 · Market data & dashboard
                </div>
              </section>
            </aside>
          </div>
          <section className="panel evidence-panel">
            <div className="evidence-tabs">
              <div>
                <button
                  className={tab === "observations" ? "active" : ""}
                  onClick={() => setTab("observations")}
                >
                  <Activity size={14} />
                  Observation ledger<span>{shown.receipts.length}</span>
                </button>
                <button
                  className={tab === "pipeline" ? "active" : ""}
                  onClick={() => setTab("pipeline")}
                >
                  <Layers3 size={14} />
                  Data pipeline
                </button>
              </div>
              <span className="ledger-label">
                {mode === "replay"
                  ? "RECORDED RECEIPTS"
                  : "LATEST PERSISTED RECEIPTS"}
              </span>
            </div>
            {tab === "observations" ? (
              <div className="table-scroll">
                <table>
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
                    {shown.receipts.slice(0, 5).map((r) => (
                      <tr key={r.receiptId}>
                        <td>
                          <span className="receipt-number">#{r.receiptId}</span>
                          <span title={r.logicalId} className="identity">
                            {r.symbol} · {r.interval}
                          </span>
                        </td>
                        <td>
                          <span className="source-cell">
                            <span className="dot muted-dot" />
                            {r.source}
                          </span>
                        </td>
                        <td>{time(r.sourceTime)}</td>
                        <td>{time(r.receiptTime)}</td>
                        <td>${money(r.price ?? r.close)}</td>
                        <td>
                          <span className="revision">v{r.revision}</span>
                        </td>
                        <td>
                          <span className={`disposition ${r.disposition}`}>
                            {r.kind === "candle" && !r.complete
                              ? "forming · "
                              : ""}
                            {r.disposition}
                          </span>
                        </td>
                      </tr>
                    ))}
                    {!shown.receipts.length && (
                      <tr>
                        <td colSpan={7} className="empty-ledger">
                          Waiting for persisted observations. No generated
                          prices are used.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="pipeline">
                <div>
                  <Globe2 />
                  <strong>01 · Yahoo Finance</strong>
                  <span>WebSocket quotes + chart OHLCV</span>
                </div>
                <ChevronRight />
                <div>
                  <Database />
                  <strong>02 · SQLite commit</strong>
                  <span>
                    {count(stats.receipts)} receipts · revisions preserved
                  </span>
                </div>
                <ChevronRight />
                <div>
                  <Wifi />
                  <strong>03 · Server WebSocket</strong>
                  <span>
                    {connected ? "Browser connected" : "Browser reconnecting"} ·
                    /ws
                  </span>
                </div>
                <ChevronRight />
                <div>
                  <ChartCandlestick />
                  <strong>04 · Live chart</strong>
                  <span>{shown.candles.length} one-minute candles</span>
                </div>
              </div>
            )}
          </section>
          <footer className="page-footer">
            <span>
              <Activity size={12} />
              MARKETSTATION<span>/</span>Live data. Recorded faithfully.
            </span>
            <div>
              {demo && (
                <button disabled={busy} onClick={toggleFeed}>
                  {feed.paused ? <Wifi size={12} /> : <Unplug size={12} />}{" "}
                  {feed.paused
                    ? "Reconnect Yahoo feed"
                    : "Demonstrate feed outage"}
                </button>
              )}
              <a
                href="https://www.tradingview.com/"
                target="_blank"
                rel="noreferrer"
              >
                Charts by TradingView ↗
              </a>
              <a
                href="https://github.com/abn54/Live-Marketstation-"
                target="_blank"
                rel="noreferrer"
              >
                View source ↗
              </a>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
}
const mount = document.getElementById("root")! as HTMLElement & {
  workstationRoot?: Root;
};
mount.workstationRoot ??= createRoot(mount);
mount.workstationRoot.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
