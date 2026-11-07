import test from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { decodeQuote, normalizeChart, YahooFeed } from "../server/yahoo.js";
import { MarketStore } from "../server/store.js";
import protobuf from "protobufjs";
import { fileURLToPath } from "node:url";
const type = protobuf
  .loadSync(fileURLToPath(new URL("../server/pricing.proto", import.meta.url)))
  .lookupType("PricingData");
const t = 1794009600000;
const response = () => ({
  chart: {
    result: [
      {
        meta: { shortName: "Bitcoin USD", currency: "USD" },
        timestamp: [t / 1000, t / 1000 + 60, t / 1000 + 75],
        indicators: {
          quote: [
            {
              open: [100, 102, 103],
              high: [104, 105, 103],
              low: [99, 101, 103],
              close: [102, 104, 103],
              volume: [50, 70, 0],
            },
          ],
        },
      },
    ],
    error: null,
  },
});
test("Yahoo protobuf envelope decodes price, provider milliseconds and provenance", () => {
  const encoded = type
    .encode(
      type.create({
        id: "BTC-USD",
        price: 100.5,
        time: t,
        currency: "USD",
        dayVolume: 1000,
      }),
    )
    .finish();
  const q = decodeQuote(
    JSON.stringify({
      type: "pricing",
      message: Buffer.from(encoded).toString("base64"),
    }),
    t + 1000,
  );
  assert.equal(q.sourceTime, t);
  assert.equal(q.payload.price, 100.5);
  assert.equal(q.receivedAt, t + 1000);
  assert.equal(q.payload.dayVolume, 1000);
  assert.equal(q.source, "yahoo-stream");
});
test("normalizer preserves official OHLCV over appended last-price row, completes only earlier bars", () => {
  const a = normalizeChart(
    response(),
    "BTC-USD",
    t + 90000,
    t + 91000,
  ).observations;
  assert.equal(a.length, 2);
  assert.equal(a[0].payload.complete, true);
  assert.equal(a[1].payload.complete, false);
  assert.equal(a[1].payload.volume, 70);
  assert.equal(a[1].payload.close, 104);
  assert.equal(a[1].orderingTime, t + 90000);
});
test("invalid prices are omitted, unreported volume stays null", () => {
  const d = response();
  d.chart.result[0].indicators.quote[0].volume[0] = null;
  d.chart.result[0].indicators.quote[0].open[1] = null;
  d.chart.result[0].indicators.quote[0].open[2] = null;
  const a = normalizeChart(d, "BTC-USD", t + 90000, t + 91000).observations;
  assert.equal(a.length, 1);
  assert.equal(a[0].payload.volume, null);
});
test("Yahoo error payload and corrupt protocol fail visibly", () => {
  assert.throws(
    () =>
      normalizeChart(
        { chart: { error: { description: "Rate limited" } } },
        "BTC-USD",
        t,
        t,
      ),
    /Rate limited/,
  );
  assert.throws(() => decodeQuote("{broken"), SyntaxError);
});
test("HTTP 429 is unavailable, leaves prior observations intact, and can recover", async () => {
  const s = new MarketStore(":memory:");
  let fail = true;
  const f = new YahooFeed({
    store: s,
    now: () => t + 90000,
    fetchImpl: async () =>
      fail
        ? { ok: false, status: 429 }
        : { ok: true, json: async () => response() },
  });
  f.stopped = false;
  try {
    await f.fetchSymbol("BTC-USD");
    assert.equal(f.symbols["BTC-USD"].chartState, "unavailable");
    assert.match(f.symbols["BTC-USD"].chartError, /429/);
    assert.equal(s.stats().observations, 0);
    fail = false;
    await f.fetchSymbol("BTC-USD");
    assert.equal(s.stats().observations, 2);
    fail = true;
    await f.fetchSymbol("BTC-USD");
    assert.equal(s.candles("BTC-USD").length, 2);
  } finally {
    f.stop();
    s.close();
  }
});
test("outage during an in-flight fetch cannot leak new rows or a healthy status", async () => {
  const s = new MarketStore(":memory:");
  let resolve;
  const pending = new Promise((r) => (resolve = r));
  const f = new YahooFeed({
    store: s,
    now: () => t + 90000,
    fetchImpl: () => pending,
  });
  f.stopped = false;
  const task = f.fetchSymbol("BTC-USD");
  f.pause();
  resolve({ ok: true, json: async () => response() });
  await task;
  try {
    assert.equal(s.stats().observations, 0);
    assert.equal(f.status().chart.state, "unavailable");
    assert.equal(f.status().paused, true);
  } finally {
    f.stop();
    s.close();
  }
});
test("WebSocket quote is committed before onData; socket close exposes retry state", () => {
  const s = new MarketStore(":memory:");
  class Socket extends EventEmitter {
    readyState = 1;
    send() {}
    terminate() {}
  }
  const ws = new Socket();
  let committed = false;
  const f = new YahooFeed({
    store: s,
    now: () => t + 1000,
    webSocketFactory: () => ws,
    onData: (results) => {
      committed =
        s.stats().observations === 1 &&
        results[0].observation.id === s.quote("BTC-USD").id;
    },
  });
  f.stopped = false;
  try {
    f.connect();
    ws.emit("open");
    const message = type
      .encode(type.create({ id: "BTC-USD", price: 101, time: t }))
      .finish();
    ws.emit(
      "message",
      JSON.stringify({
        type: "pricing",
        message: Buffer.from(message).toString("base64"),
      }),
    );
    assert.equal(committed, true);
    assert.equal(f.status().stream.state, "streaming");
    ws.emit("close");
    assert.equal(f.status().stream.state, "unavailable");
    assert.match(f.status().stream.detail, /retry/);
  } finally {
    f.stop();
    s.close();
  }
});
test("repeated reconnect is idempotent and does not create extra Yahoo sockets", () => {
  const s = new MarketStore(":memory:");
  let connects = 0;
  class Socket extends EventEmitter {
    terminate() {}
  }
  const f = new YahooFeed({
    store: s,
    webSocketFactory: () => {
      connects++;
      return new Socket();
    },
  });
  f.stopped = false;
  f.paused = true;
  f.poll = () => {};
  try {
    f.resume();
    f.resume();
    assert.equal(connects, 1);
  } finally {
    f.stop();
    s.close();
  }
});
