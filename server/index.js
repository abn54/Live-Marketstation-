import { existsSync } from "node:fs";
import { resolve } from "node:path";
import express from "express";
import { MarketStore } from "./store.js";
import { createApp } from "./app.js";
if (existsSync(".env")) process.loadEnvFile(".env");
const port = Number(process.env.PORT ?? 3000),
  host = process.env.HOST ?? "127.0.0.1";
const pollMs = Number(process.env.POLL_INTERVAL_MS ?? 15000);
if (
  !Number.isInteger(port) ||
  port < 1 ||
  port > 65535 ||
  !Number.isFinite(pollMs) ||
  pollMs < 10000
)
  throw new Error("PORT must be 1–65535; POLL_INTERVAL_MS must be >=10000");
const path = process.env.DATABASE_PATH ?? "./data/market.sqlite";
const store = new MarketStore(path);
const runtime = createApp({
  store,
  demoControls: process.env.ENABLE_DEMO_CONTROLS === "true",
  pollMs,
});
let vite;
if (process.env.NODE_ENV === "production") {
  if (!existsSync("dist/index.html"))
    throw new Error("Run npm run build before npm start");
  runtime.app.use(express.static(resolve("dist")));
  runtime.app.get("/{*path}", (req, res) =>
    res.sendFile(resolve("dist/index.html")),
  );
} else {
  const { createServer } = await import("vite");
  vite = await createServer({
    server: { middlewareMode: true },
    appType: "spa",
  });
  runtime.app.use(vite.middlewares);
}
runtime.server.listen(port, host, () => {
  console.log(
    `Marketstation: http://${host}:${port}\nSQLite: ${resolve(path)}\nDemo controls: ${process.env.ENABLE_DEMO_CONTROLS === "true" ? "enabled" : "disabled"}`,
  );
  runtime.feed.start();
});
let closing = false;
async function shutdown() {
  if (closing) return;
  closing = true;
  await runtime.close();
  await vite?.close();
  store.close();
  process.exit(0);
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
