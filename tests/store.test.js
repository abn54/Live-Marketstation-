import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { MarketStore } from "../server/store.js";
const t = 1794009600000;
const candle = (changes = {}) => ({
  source: "yahoo-chart",
  kind: "candle",
  symbol: "BTC-USD",
  interval: "1m",
  sourceTime: t,
  receivedAt: t + 30000,
  orderingTime: t + 25000,
  payload: {
    open: 100,
    high: 103,
    low: 99,
    close: 102,
    volume: 10,
    complete: false,
  },
  ...changes,
});
function storeTest(name, fn) {
  test(name, () => {
    const s = new MarketStore(":memory:");
    try {
      fn(s);
    } finally {
      s.close();
    }
  });
}
storeTest(
  "exact duplicate preserves one observation and two receipt identities",
  (s) => {
    const a = s.ingestBatch([candle()])[0],
      b = s.ingestBatch([
        candle({ receivedAt: t + 35000, orderingTime: t + 34000 }),
      ])[0];
    assert.equal(b.disposition, "duplicate");
    assert.equal(a.observation.id, b.observation.id);
    assert.notEqual(a.receiptId, b.receiptId);
    assert.equal(s.stats().observations, 1);
    assert.equal(s.stats().receipts, 2);
    assert.equal(s.replay("BTC-USD")[1].orderingTime, t + 34000);
  },
);
storeTest("payload property order does not create a false revision", (s) => {
  s.ingestBatch([candle()]);
  const o = candle();
  o.payload = Object.fromEntries(Object.entries(o.payload).reverse());
  assert.equal(s.ingestBatch([o])[0].disposition, "duplicate");
});
storeTest(
  "changed OHLCV creates immutable revision and promotes current head",
  (s) => {
    const a = s.ingestBatch([candle()])[0];
    const o = candle({ receivedAt: t + 40000, orderingTime: t + 39000 });
    o.payload = { ...o.payload, high: 105, close: 104, volume: 15 };
    const b = s.ingestBatch([o])[0];
    assert.equal(b.disposition, "revised");
    assert.equal(b.observation.revision, 2);
    assert.equal(s.candles("BTC-USD")[0].close, 104);
    assert.equal(s.replay("BTC-USD")[0].observation.close, a.observation.close);
  },
);
storeTest(
  "out-of-order response is preserved but cannot replace a newer snapshot",
  (s) => {
    s.ingestBatch([candle({ orderingTime: t + 29000 })]);
    const o = candle({ orderingTime: t + 20000, receivedAt: t + 40000 });
    o.payload = { ...o.payload, close: 101 };
    const r = s.ingestBatch([o])[0];
    assert.equal(r.disposition, "superseded");
    assert.equal(r.applied, false);
    assert.equal(s.candles("BTC-USD")[0].close, 102);
    assert.equal(s.stats().observations, 2);
    assert.equal(s.stats().superseded, 1);
  },
);
storeTest(
  "newer duplicate advances watermark and blocks slow old differing response",
  (s) => {
    s.ingestBatch([candle()]);
    s.ingestBatch([candle({ orderingTime: t + 40000, receivedAt: t + 41000 })]);
    const old = candle({ orderingTime: t + 35000, receivedAt: t + 42000 });
    old.payload = { ...old.payload, close: 101 };
    assert.equal(s.ingestBatch([old])[0].disposition, "superseded");
    assert.equal(s.candles("BTC-USD")[0].close, 102);
  },
);
storeTest(
  "return to an earlier value with a newer request is a legitimate revision",
  (s) => {
    const a = candle();
    s.ingestBatch([a]);
    const b = candle({ orderingTime: t + 35000, receivedAt: t + 36000 });
    b.payload = { ...b.payload, close: 101 };
    s.ingestBatch([b]);
    const r = s.ingestBatch([
      candle({ orderingTime: t + 40000, receivedAt: t + 41000 }),
    ])[0];
    assert.equal(r.disposition, "revised");
    assert.equal(r.observation.revision, 3);
    assert.equal(s.candles("BTC-USD")[0].close, 102);
  },
);
storeTest(
  "completion is a persisted revision and an older partial cannot reopen it",
  (s) => {
    s.ingestBatch([candle()]);
    const done = candle({ orderingTime: t + 70000, receivedAt: t + 71000 });
    done.payload = { ...done.payload, complete: true };
    s.ingestBatch([done]);
    const late = candle({ orderingTime: t + 50000, receivedAt: t + 72000 });
    late.payload = { ...late.payload, close: 101 };
    assert.equal(s.ingestBatch([late])[0].disposition, "superseded");
    assert.equal(s.candles("BTC-USD")[0].complete, true);
  },
);
storeTest(
  "late older minute inserts chronologically without corrupting the latest minute",
  (s) => {
    s.ingestBatch([
      candle({
        sourceTime: t + 60000,
        orderingTime: t + 80000,
        receivedAt: t + 81000,
      }),
    ]);
    s.ingestBatch([candle({ orderingTime: t + 82000, receivedAt: t + 83000 })]);
    assert.deepEqual(
      s.candles("BTC-USD").map((o) => o.sourceTime),
      [t, t + 60000],
    );
  },
);
storeTest(
  "replay uses receipt order, frozen high watermark, duplicates and superseded records",
  (s) => {
    s.ingestBatch([candle()]);
    s.ingestBatch([candle({ receivedAt: t + 40000 })]);
    const high = s.stats().lastReceiptId;
    const late = candle({ orderingTime: t + 20000, receivedAt: t + 45000 });
    late.payload = { ...late.payload, close: 101 };
    s.ingestBatch([late]);
    const page = s.replay("BTC-USD", { until: high, limit: 1 });
    const page2 = s.replay("BTC-USD", {
      after: page[0].receiptId,
      until: high,
    });
    assert.equal(page2.length, 1);
    assert.equal(page2[0].disposition, "duplicate");
    assert.equal(page2[0].receivedAt, t + 40000);
    assert.equal(s.replay("BTC-USD")[2].applied, false);
  },
);
storeTest(
  "invalid batch cannot partially persist; volume null differs from zero",
  (s) => {
    const invalid = candle();
    invalid.payload = { ...invalid.payload, high: 1 };
    assert.throws(() => s.ingestBatch([candle(), invalid]), /bounds/);
    assert.equal(s.stats().observations, 0);
    const o = candle();
    o.payload = { ...o.payload, volume: null };
    s.ingestBatch([o]);
    assert.equal(s.candles("BTC-USD")[0].volume, null);
  },
);
storeTest(
  "latest quote follows source time when an older quote arrives late",
  (s) => {
    const quote = (sourceTime, price, receivedAt) => ({
      source: "yahoo-stream",
      kind: "quote",
      symbol: "BTC-USD",
      interval: "tick",
      sourceTime,
      receivedAt,
      orderingTime: receivedAt,
      payload: { price },
    });
    s.ingestBatch([quote(t + 2000, 103, t + 3000)]);
    s.ingestBatch([quote(t + 1000, 101, t + 4000)]);
    assert.equal(s.quote("BTC-USD").price, 103);
  },
);
test("database survives close and reopen with revisions and receipts intact", () => {
  const dir = mkdtempSync(join(tmpdir(), "marketstation-")),
    path = join(dir, "market.sqlite");
  let s = new MarketStore(path);
  try {
    s.ingestBatch([candle()]);
    s.close();
    s = new MarketStore(path);
    assert.equal(s.candles("BTC-USD")[0].close, 102);
    assert.equal(s.stats().receipts, 1);
    assert.equal(
      s.db.prepare("PRAGMA integrity_check").get().integrity_check,
      "ok",
    );
  } finally {
    s.close();
    rmSync(dir, { recursive: true });
  }
});
