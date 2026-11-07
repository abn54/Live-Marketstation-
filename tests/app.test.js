import test from "node:test";
import assert from "node:assert/strict";
import WebSocket from "ws";
import { once } from "node:events";
import { MarketStore } from "../server/store.js";
import { createApp } from "../server/app.js";
function fakeFeed(options) {
  return {
    options,
    status: () => ({
      stream: { state: "unavailable", detail: "test unavailable" },
      chart: { state: "unavailable", detail: "test unavailable" },
      symbols: {},
      paused: false,
    }),
    pause() {
      this.paused = true;
    },
    resume() {
      this.paused = false;
    },
    stop() {},
  };
}
async function withApp(fn, demoControls = false) {
  const store = new MarketStore(":memory:");
  const runtime = createApp({ store, demoControls, feedFactory: fakeFeed });
  runtime.server.listen(0, "127.0.0.1");
  await once(runtime.server, "listening");
  const base = `http://127.0.0.1:${runtime.server.address().port}`;
  try {
    await fn({ base, store, ...runtime });
  } finally {
    await runtime.close();
    store.close();
  }
}
test("health exposes unavailable upstream while server and SQLite remain healthy", () =>
  withApp(async ({ base }) => {
    const r = await fetch(`${base}/api/health`);
    const h = await r.json();
    assert.equal(h.ok, true);
    assert.equal(h.feed.stream.state, "unavailable");
    assert.equal(h.stats.observations, 0);
  }));
test("invalid symbols and pagination rejected; unknown APIs are JSON 404", () =>
  withApp(async ({ base }) => {
    for (const path of [
      "/api/candles?symbol=INVALID",
      "/api/replay?symbol=BTC-USD&after=-1",
      "/api/replay?symbol=BTC-USD&limit=100000",
      "/api/replay?symbol=BTC-USD&limit=0",
      "/api/candles?symbol=BTC-USD&limit=NaN",
    ])
      assert.equal((await fetch(base + path)).status, 400);
    assert.equal((await fetch(base + "/api/missing")).status, 404);
  }));
test("fault controls disabled by default and cross-origin requests rejected when enabled", async () => {
  await withApp(async ({ base }) =>
    assert.equal(
      (
        await fetch(base + "/api/demo/feed", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: '{"action":"disconnect"}',
        })
      ).status,
      403,
    ),
  );
  await withApp(
    async ({ base }) =>
      assert.equal(
        (
          await fetch(base + "/api/demo/feed", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Origin: "https://untrusted.example",
            },
            body: '{"action":"disconnect"}',
          })
        ).status,
        403,
      ),
    true,
  );
});
test("local demo action disconnects and reconnects the feed", () =>
  withApp(async ({ base, feed }) => {
    for (const action of ["disconnect", "reconnect"]) {
      const r = await fetch(base + "/api/demo/feed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      assert.equal(r.status, 200);
      assert.equal(feed.paused, action === "disconnect");
    }
  }, true));
test("real client WebSocket snapshot, persisted update, and REST retrieval agree", () =>
  withApp(async ({ base, feed, store }) => {
    const ws = new WebSocket(base.replace("http:", "ws:") + "/ws");
    try {
      const [message] = await once(ws, "message");
      const snapshot = JSON.parse(message);
      assert.equal(snapshot.type, "snapshot");
      assert.equal(snapshot.symbols.length, 4);
      const t = 1794009600000;
      const results = store.ingestBatch([
        {
          source: "yahoo-chart",
          kind: "candle",
          symbol: "BTC-USD",
          interval: "1m",
          sourceTime: t,
          receivedAt: t + 10000,
          orderingTime: t + 9000,
          payload: {
            open: 100,
            high: 102,
            low: 99,
            close: 101,
            volume: 50,
            complete: false,
          },
        },
      ]);
      const pending = once(ws, "message");
      feed.options.onData(results);
      const [raw] = await pending;
      const event = JSON.parse(raw);
      assert.equal(event.type, "observations");
      assert.equal(event.results[0].observation.id, results[0].observation.id);
      const d = await (
        await fetch(base + "/api/candles?symbol=BTC-USD")
      ).json();
      assert.equal(d.candles[0].id, event.results[0].observation.id);
      assert.equal(d.candles[0].volume, 50);
      const replay = await (
        await fetch(base + "/api/replay?symbol=BTC-USD")
      ).json();
      assert.equal(replay.records[0].receiptId, event.results[0].receiptId);
      assert.equal(replay.mode, "recorded");
    } finally {
      ws.terminate();
    }
  }));
