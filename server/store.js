import { DatabaseSync } from "node:sqlite";
import { mkdirSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { createHash } from "node:crypto";

export function validateObservation(o) {
  if (
    !["candle", "quote"].includes(o.kind) ||
    !/^[A-Z0-9^=.-]{1,24}$/.test(o.symbol)
  )
    throw new Error("Invalid observation identity");
  if (!["yahoo-chart", "yahoo-stream"].includes(o.source))
    throw new Error("Invalid observation source");
  for (const key of ["sourceTime", "receivedAt", "orderingTime"])
    if (!Number.isSafeInteger(o[key]) || o[key] < 0)
      throw new Error(`Invalid ${key}`);
  if (o.sourceTime > o.receivedAt + 300000)
    throw new Error("Source timestamp is too far in the future");
  const p = o.payload;
  if (o.kind === "candle") {
    if (o.interval !== "1m" || o.sourceTime % 60000 !== 0)
      throw new Error("Candle must be aligned to one minute");
    if (
      ![p.open, p.high, p.low, p.close].every(
        (v) => Number.isFinite(v) && v > 0,
      )
    )
      throw new Error("Invalid OHLC");
    if (
      p.high < Math.max(p.open, p.close, p.low) ||
      p.low > Math.min(p.open, p.close, p.high)
    )
      throw new Error("Invalid OHLC bounds");
    if (p.volume !== null && (!Number.isFinite(p.volume) || p.volume < 0))
      throw new Error("Invalid volume");
    if (typeof p.complete !== "boolean")
      throw new Error("Missing candle completeness");
  } else if (!Number.isFinite(p.price) || p.price <= 0)
    throw new Error("Invalid price");
}
export const hydrate = (row) =>
  row
    ? {
        id: row.id,
        logicalId: row.logical_id,
        revision: row.revision,
        source: row.source,
        kind: row.kind,
        symbol: row.symbol,
        interval: row.interval,
        sourceTime: row.source_time,
        receivedAt: row.received_at,
        orderingTime: row.ordering_time,
        ...JSON.parse(row.payload_json),
      }
    : null;

export class MarketStore {
  constructor(path = "./data/market.sqlite") {
    if (path !== ":memory:")
      mkdirSync(dirname(resolve(path)), { recursive: true });
    this.db = new DatabaseSync(path);
    this.db.exec(
      "PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; PRAGMA synchronous=FULL;",
    );
    this.db.exec(
      readFileSync(new URL("./schema.sql", import.meta.url), "utf8"),
    );
  }
  ingestBatch(observations) {
    // Validate the whole batch before beginning the transaction.
    observations.forEach(validateObservation);
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const result = observations.map((o) => this.ingestOne(o));
      this.db.exec("COMMIT");
      return result;
    } catch (e) {
      this.db.exec("ROLLBACK");
      throw e;
    }
  }
  ingestOne(o) {
    const logicalId = `${o.source}:${o.kind}:${o.symbol}:${o.interval}:${o.sourceTime}`;
    // Normalizers construct keys in a fixed order; hash only market content, never receipt time.
    const payloadJson = JSON.stringify(
      o.payload,
      Object.keys(o.payload).sort(),
    );
    const hash = createHash("sha256").update(payloadJson).digest("hex");
    const head = this.db
      .prepare(
        "SELECT o.*,h.ordering_time AS head_order FROM heads h JOIN observations o ON o.id=h.observation_id WHERE h.logical_id=?",
      )
      .get(logicalId);
    let existing = head?.payload_hash === hash ? head : null;
    if (!existing && head && o.orderingTime < head.head_order)
      existing = this.db
        .prepare(
          "SELECT * FROM observations WHERE logical_id=? AND payload_hash=? ORDER BY id DESC LIMIT 1",
        )
        .get(logicalId, hash);
    let disposition,
      applied = false,
      id;
    if (existing) {
      id = existing.id;
      disposition = "duplicate";
    } else {
      const revision = this.db
        .prepare(
          "SELECT COALESCE(MAX(revision),0)+1 AS n FROM observations WHERE logical_id=?",
        )
        .get(logicalId).n;
      id = Number(
        this.db
          .prepare(
            "INSERT INTO observations(logical_id,revision,source,kind,symbol,interval,source_time,received_at,ordering_time,payload_hash,payload_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
          )
          .run(
            logicalId,
            revision,
            o.source,
            o.kind,
            o.symbol,
            o.interval,
            o.sourceTime,
            o.receivedAt,
            o.orderingTime,
            hash,
            payloadJson,
          ).lastInsertRowid,
      );
      applied = !head || o.orderingTime >= head.head_order;
      disposition = !applied ? "superseded" : head ? "revised" : "inserted";
    }
    // A duplicate still advances the request-order watermark. A slow older request
    // must not overwrite a newer unchanged fetch.
    if (applied || (existing && o.orderingTime >= head.head_order))
      this.db
        .prepare(
          "INSERT INTO heads VALUES (?,?,?) ON CONFLICT(logical_id) DO UPDATE SET observation_id=excluded.observation_id,ordering_time=excluded.ordering_time",
        )
        .run(logicalId, id, o.orderingTime);
    const receiptId = Number(
      this.db
        .prepare(
          "INSERT INTO receipts(observation_id,received_at,ordering_time,disposition,applied) VALUES (?,?,?,?,?)",
        )
        .run(id, o.receivedAt, o.orderingTime, disposition, Number(applied))
        .lastInsertRowid,
    );
    return {
      receiptId,
      receivedAt: o.receivedAt,
      disposition,
      applied,
      observation: hydrate(
        this.db.prepare("SELECT * FROM observations WHERE id=?").get(id),
      ),
    };
  }
  candles(symbol, limit = 360) {
    return this.db
      .prepare(
        "SELECT o.* FROM heads h JOIN observations o ON o.id=h.observation_id WHERE o.kind='candle' AND o.symbol=? ORDER BY o.source_time DESC LIMIT ?",
      )
      .all(symbol, limit)
      .reverse()
      .map(hydrate);
  }
  quote(symbol) {
    return hydrate(
      this.db
        .prepare(
          "SELECT o.* FROM heads h JOIN observations o ON o.id=h.observation_id WHERE o.kind='quote' AND o.symbol=? ORDER BY o.source_time DESC,o.id DESC LIMIT 1",
        )
        .get(symbol),
    );
  }
  recent(symbol, limit = 12) {
    return this.db
      .prepare(
        "SELECT r.id AS receipt_id,r.disposition,r.received_at AS receipt_time,o.* FROM receipts r JOIN observations o ON o.id=r.observation_id WHERE o.symbol=? ORDER BY r.id DESC LIMIT ?",
      )
      .all(symbol, limit)
      .map((r) => ({
        ...hydrate(r),
        receiptId: r.receipt_id,
        disposition: r.disposition,
        receiptTime: r.receipt_time,
      }));
  }
  replay(
    symbol,
    { after = 0, until = Number.MAX_SAFE_INTEGER, limit = 500 } = {},
  ) {
    return this.db
      .prepare(
        "SELECT r.id AS receipt_id,r.received_at AS receipt_time,r.disposition,r.applied,r.ordering_time AS receipt_ordering_time,o.* FROM receipts r JOIN observations o ON o.id=r.observation_id WHERE o.symbol=? AND r.id>? AND r.id<=? ORDER BY r.id LIMIT ?",
      )
      .all(symbol, after, until, limit)
      .map((r) => ({
        receiptId: r.receipt_id,
        receivedAt: r.receipt_time,
        orderingTime: r.receipt_ordering_time,
        disposition: r.disposition,
        applied: Boolean(r.applied),
        observation: hydrate(r),
      }));
  }
  stats() {
    return {
      ...this.db
        .prepare(
          "SELECT COUNT(*) AS observations,COALESCE(SUM(revision>1),0) AS revisions FROM observations",
        )
        .get(),
      ...this.db
        .prepare(
          "SELECT COUNT(*) AS receipts,COALESCE(SUM(disposition='duplicate'),0) AS duplicates,COALESCE(SUM(disposition='superseded'),0) AS superseded,COALESCE(MAX(id),0) AS lastReceiptId FROM receipts",
        )
        .get(),
      candles: this.db
        .prepare(
          "SELECT COUNT(*) AS n FROM heads h JOIN observations o ON o.id=h.observation_id WHERE kind='candle'",
        )
        .get().n,
      journalMode: this.db.prepare("PRAGMA journal_mode").get().journal_mode,
    };
  }
  event(channel, state, detail, now = Date.now()) {
    this.db
      .prepare(
        "INSERT INTO feed_events(received_at,channel,state,detail) VALUES (?,?,?,?)",
      )
      .run(now, channel, state, detail);
  }
  events(limit = 10) {
    return this.db
      .prepare("SELECT * FROM feed_events ORDER BY id DESC LIMIT ?")
      .all(limit);
  }
  close() {
    this.db.close();
  }
}
