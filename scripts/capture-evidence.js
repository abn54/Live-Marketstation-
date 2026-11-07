import { writeFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { once } from "node:events";
import assert from "node:assert/strict";
import WebSocket from "ws";
const base = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const db = new DatabaseSync(
  process.env.DATABASE_PATH ?? "./data/market.sqlite",
  { readOnly: true },
);
const get = async (path) => {
  const r = await fetch(base + path);
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return r.json();
};
const action = async (action) => {
  const r = await fetch(base + "/api/demo/feed", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  if (!r.ok)
    throw new Error(
      "Start with ENABLE_DEMO_CONTROLS=true to capture outage evidence",
    );
  return r.json();
};
const evidence = {
  capturedAt: new Date().toISOString(),
  origin: "Actual Yahoo Finance network observations; no synthetic prices",
  checks: [],
};
const check = (name, fn) => {
  fn();
  evidence.checks.push({ name, passed: true });
};
const ws = new WebSocket(base.replace(/^http/, "ws") + "/ws");
const messages = [];
ws.on("message", (raw) => {
  const m = JSON.parse(raw);
  if (m.type === "observations") messages.push(...m.results);
});
try {
  await once(ws, "open");
  evidence.before = await get("/api/health");
  check("Running app uses Vue, FastAPI, and SQLite", () =>
    assert.deepEqual(evidence.before.stack, {
      frontend: "Vue 3",
      backend: "FastAPI",
      database: "SQLite",
    }),
  );
  console.log(
    "Collecting a fresh Yahoo quote and applied candle update (up to 45 seconds)…",
  );
  const deadline = Date.now() + 45000;
  while (
    Date.now() < deadline &&
    (!messages.some((r) => r.observation.kind === "quote") ||
      !messages.some((r) => r.observation.kind === "candle" && r.applied))
  )
    await new Promise((r) => setTimeout(r, 250));
  const quote = messages.find((r) => r.observation.kind === "quote"),
    candle = messages.find((r) => r.observation.kind === "candle" && r.applied);
  check("Live Yahoo quote reached the client WebSocket", () =>
    assert.ok(quote),
  );
  check("Yahoo candle reached the client WebSocket", () => assert.ok(candle));
  check("Yahoo quote source timestamp is current", () => {
    assert.equal(quote.observation.source, "yahoo-stream");
    assert.ok(
      quote.observation.sourceTime >= evidence.before.serverTime - 60000,
    );
  });
  evidence.clientWebSocket = { quote, candle };
  for (const item of [quote, candle]) {
    const row = db
      .prepare("SELECT * FROM observations WHERE id=?")
      .get(item.observation.id);
    check(
      `WebSocket observation ${row.id} matches committed SQLite content`,
      () => {
        assert.equal(row.logical_id, item.observation.logicalId);
        assert.equal(row.source_time, item.observation.sourceTime);
        assert.equal(
          JSON.parse(row.payload_json)[
            item.observation.kind === "quote" ? "price" : "close"
          ],
          item.observation.price ?? item.observation.close,
        );
      },
    );
  }
  evidence.databaseSamples = [quote, candle].map((r) =>
    db.prepare("SELECT * FROM observations WHERE id=?").get(r.observation.id),
  );
  evidence.outage = await action("disconnect");
  const paused = await get("/api/health");
  const retained = await get("/api/candles?symbol=BTC-USD");
  const frozenCount = paused.stats.observations;
  await new Promise((r) => setTimeout(r, 1250));
  const later = await get("/api/health");
  check("Unavailable-feed state is explicit for both upstream channels", () => {
    assert.equal(later.feed.stream.state, "unavailable");
    assert.equal(later.feed.chart.state, "unavailable");
  });
  check("Unavailable feed does not generate observations", () =>
    assert.equal(later.stats.observations, frozenCount),
  );
  check("Chart history remains retrievable while Yahoo is disconnected", () =>
    assert.ok(retained.candles.length > 0),
  );
  evidence.outageHealth = later;
  const high = later.stats.lastReceiptId;
  let after = 0,
    all = [];
  for (;;) {
    const page = await get(
      `/api/replay?symbol=BTC-USD&after=${after}&until=${high}&limit=2000`,
    );
    all.push(...page.records);
    after = page.nextAfter;
    if (page.done) break;
  }
  const heads = new Map();
  for (const record of all)
    if (record.applied)
      heads.set(record.observation.logicalId, record.observation);
  const reconstructed = [...heads.values()]
    .filter((o) => o.kind === "candle")
    .sort((a, b) => a.sourceTime - b.sourceTime)
    .slice(-360);
  check(
    "Receipt-order replay exactly reconstructs current persisted candles",
    () =>
      assert.deepEqual(
        reconstructed.map((o) => [o.id, o.close, o.volume, o.complete]),
        retained.candles.map((o) => [o.id, o.close, o.volume, o.complete]),
      ),
  );
  check("Replay is read-only", () =>
    assert.equal(
      db.prepare("SELECT COUNT(*) AS n FROM observations").get().n,
      frozenCount,
    ),
  );
  evidence.replay = {
    symbol: "BTC-USD",
    receipts: all.length,
    until: high,
    candles: reconstructed.length,
    mode: "recorded",
  };
  // A bounded, genuine recording for offline development: bootstrap candles plus
  // subsequent receipts, excluding redundant historical duplicates only.
  const keep = all.filter(
    (r) => r.disposition !== "duplicate" || r.observation.kind === "quote",
  );
  const recording = {
    formatVersion: 1,
    capturedAt: evidence.capturedAt,
    source: "Yahoo Finance",
    description:
      "Genuine recorded BTC-USD receipts. Original source and receipt times retained. Historical duplicate receipts omitted to keep the fixture compact.",
    records: keep,
  };
  writeFileSync(
    "evidence/btc-recording.json",
    JSON.stringify(recording, null, 2) + "\n",
  );
  await action("reconnect");
  const recoveryDeadline = Date.now() + 30000;
  let recovered;
  do {
    await new Promise((r) => setTimeout(r, 500));
    recovered = await get("/api/health");
  } while (
    Date.now() < recoveryDeadline &&
    (recovered.feed.stream.state !== "streaming" ||
      recovered.feed.chart.state !== "available")
  );
  check("Yahoo live collection recovers after reconnection", () => {
    assert.equal(recovered.feed.stream.state, "streaming");
    assert.equal(recovered.feed.chart.state, "available");
    assert.equal(recovered.feed.paused, false);
  });
  evidence.after = recovered;
  evidence.integrity = db
    .prepare("PRAGMA integrity_check")
    .get().integrity_check;
  check("SQLite integrity check succeeds", () =>
    assert.equal(evidence.integrity, "ok"),
  );
  writeFileSync(
    "evidence/live-verification.json",
    JSON.stringify(evidence, null, 2) + "\n",
  );
  console.log(
    JSON.stringify(
      {
        checks: evidence.checks,
        replay: evidence.replay,
        stats: recovered.stats,
      },
      null,
      2,
    ),
  );
} finally {
  ws.terminate();
  db.close();
  await action("reconnect").catch(() => {});
}
