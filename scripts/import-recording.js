import { readFileSync, existsSync } from "node:fs";
import { MarketStore } from "../server/store.js";
if (existsSync(".env")) process.loadEnvFile(".env");
const file = process.argv[2] ?? "evidence/btc-recording.json";
const recording = JSON.parse(readFileSync(file, "utf8"));
if (recording.formatVersion !== 1 || !Array.isArray(recording.records))
  throw new Error("Unsupported recording");
const store = new MarketStore(
  process.env.DATABASE_PATH ?? "./data/market.sqlite",
);
try {
  // Re-ingest original normalized observations in their recorded receipt order.
  // Numeric local row IDs are database-local; logical source identities survive.
  for (const r of recording.records) {
    const o = r.observation;
    const payload =
      o.kind === "candle"
        ? {
            open: o.open,
            high: o.high,
            low: o.low,
            close: o.close,
            volume: o.volume,
            complete: o.complete,
          }
        : {
            price: o.price,
            currency: o.currency,
            dayVolume: o.dayVolume,
            changePercent: o.changePercent,
            exchange: o.exchange,
            marketHours: o.marketHours,
          };
    store.ingestBatch([
      {
        source: o.source,
        kind: o.kind,
        symbol: o.symbol,
        interval: o.interval,
        sourceTime: o.sourceTime,
        receivedAt: r.receivedAt,
        orderingTime: r.orderingTime ?? o.orderingTime,
        payload,
      },
    ]);
  }
  console.log(
    `Imported ${recording.records.length} recorded receipts from ${recording.source}; these remain historical, never relabeled live.`,
  );
  console.log(store.stats());
} finally {
  store.close();
}
