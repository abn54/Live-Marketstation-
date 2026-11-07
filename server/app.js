import express from "express";
import { createServer } from "node:http";
import { WebSocketServer, WebSocket } from "ws";
import { SYMBOLS, YahooFeed } from "./yahoo.js";

export function createApp({
  store,
  demoControls = false,
  pollMs = 15000,
  feedFactory = (options) => new YahooFeed(options),
}) {
  const app = express(),
    server = createServer(app),
    wss = new WebSocketServer({ noServer: true, maxPayload: 4096 });
  app.disable("x-powered-by");
  app.use(express.json({ limit: "2kb" }));
  app.use((req, res, next) => {
    res.setHeader("Cache-Control", "no-store");
    next();
  });
  const publish = (message) => {
    const data = JSON.stringify(message);
    for (const c of wss.clients)
      if (c.readyState === WebSocket.OPEN) {
        if (c.bufferedAmount > 2_000_000)
          c.close(1013, "Slow client; reconnect for snapshot");
        else c.send(data);
      }
  };
  const feed = feedFactory({
    store,
    pollMs,
    onData: (results) =>
      publish({ type: "observations", results, stats: store.stats() }),
    onStatus: (status) =>
      publish({ type: "status", status, serverTime: Date.now() }),
  });
  function symbol(req, res, next) {
    if (!SYMBOLS.includes(req.query.symbol))
      return res
        .status(400)
        .json({ error: "Choose BTC-USD, ETH-USD, SPY, or AAPL" });
    next();
  }
  function integer(value, fallback, max = Number.MAX_SAFE_INTEGER, min = 0) {
    if (value === undefined) return fallback;
    if (
      !/^\d+$/.test(String(value)) ||
      Number(value) > max ||
      Number(value) < min ||
      !Number.isSafeInteger(Number(value))
    )
      throw new Error("Invalid pagination");
    return Number(value);
  }
  app.get("/api/health", (req, res) =>
    res.json({
      ok: true,
      serverTime: Date.now(),
      stats: store.stats(),
      feed: feed.status(),
      demoControls,
    }),
  );
  app.get("/api/candles", symbol, (req, res) =>
    res.json({
      symbol: req.query.symbol,
      candles: store.candles(
        req.query.symbol,
        integer(req.query.limit, 360, 1440, 1),
      ),
      quote: store.quote(req.query.symbol),
    }),
  );
  app.get("/api/receipts", symbol, (req, res) =>
    res.json({
      receipts: store.recent(
        req.query.symbol,
        integer(req.query.limit, 12, 100, 1),
      ),
    }),
  );
  app.get("/api/events", (req, res) => res.json({ events: store.events() }));
  app.get("/api/replay", symbol, (req, res) => {
    const after = integer(req.query.after, 0),
      until = integer(req.query.until, store.stats().lastReceiptId),
      limit = integer(req.query.limit, 500, 2000, 1);
    const records = store.replay(req.query.symbol, { after, until, limit });
    res.json({
      mode: "recorded",
      symbol: req.query.symbol,
      until,
      records,
      nextAfter: records.at(-1)?.receiptId ?? after,
      done: records.length < limit,
    });
  });
  app.post("/api/demo/feed", (req, res) => {
    if (!demoControls)
      return res
        .status(403)
        .json({
          error:
            "Demo controls are disabled. Set ENABLE_DEMO_CONTROLS=true locally.",
        });
    // Prevent cross-site pages from changing the local feed.
    const origin = req.headers.origin;
    if (
      origin &&
      origin !== `http://${req.headers.host}` &&
      origin !== `https://${req.headers.host}`
    )
      return res.status(403).json({ error: "Same-origin request required" });
    if (req.body.action === "disconnect") feed.pause();
    else if (req.body.action === "reconnect") feed.resume();
    else
      return res
        .status(400)
        .json({ error: "Action must be disconnect or reconnect" });
    res.json({ feed: feed.status() });
  });
  app.use("/api", (req, res) =>
    res.status(404).json({ error: "Unknown API route" }),
  );
  app.use((err, req, res, next) =>
    res.status(400).json({ error: err.message }),
  );
  server.on("upgrade", (req, socket, head) => {
    if (req.url !== "/ws") return socket.destroy();
    if (
      req.headers.origin &&
      ![`http://${req.headers.host}`, `https://${req.headers.host}`].includes(
        req.headers.origin,
      )
    )
      return socket.destroy();
    wss.handleUpgrade(req, socket, head, (ws) =>
      wss.emit("connection", ws, req),
    );
  });
  wss.on("connection", (ws) => {
    ws.isAlive = true;
    ws.on("pong", () => (ws.isAlive = true));
    ws.on("error", () => {});
    ws.send(
      JSON.stringify({
        type: "snapshot",
        serverTime: Date.now(),
        status: feed.status(),
        stats: store.stats(),
        demoControls,
        symbols: SYMBOLS.map((symbol) => ({
          symbol,
          candles: store.candles(symbol),
          quote: store.quote(symbol),
          receipts: store.recent(symbol),
        })),
      }),
    );
  });
  const heartbeat = setInterval(() => {
    for (const ws of wss.clients) {
      if (!ws.isAlive) ws.terminate();
      else {
        ws.isAlive = false;
        ws.ping();
      }
    }
    publish({
      type: "heartbeat",
      serverTime: Date.now(),
      status: feed.status(),
      stats: store.stats(),
    });
  }, 5000);
  return {
    app,
    server,
    feed,
    wss,
    close: async () => {
      clearInterval(heartbeat);
      feed.stop();
      for (const c of wss.clients) c.terminate();
      wss.close();
      if (server.listening)
        await new Promise((resolve) => server.close(resolve));
    },
  };
}
