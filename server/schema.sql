PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, installed_at INTEGER NOT NULL);
INSERT OR IGNORE INTO schema_version VALUES (1, CAST(unixepoch('subsec') * 1000 AS INTEGER));
CREATE TABLE IF NOT EXISTS observations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  logical_id TEXT NOT NULL,
  revision INTEGER NOT NULL CHECK (revision > 0),
  source TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('candle','quote')),
  symbol TEXT NOT NULL,
  interval TEXT NOT NULL,
  source_time INTEGER NOT NULL,
  received_at INTEGER NOT NULL,
  ordering_time INTEGER NOT NULL,
  payload_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
  UNIQUE(logical_id, revision)
);
CREATE TABLE IF NOT EXISTS heads (
  logical_id TEXT PRIMARY KEY,
  observation_id INTEGER NOT NULL REFERENCES observations(id),
  ordering_time INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS receipts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  observation_id INTEGER NOT NULL REFERENCES observations(id),
  received_at INTEGER NOT NULL,
  ordering_time INTEGER NOT NULL,
  disposition TEXT NOT NULL CHECK (disposition IN ('inserted','revised','duplicate','superseded')),
  applied INTEGER NOT NULL CHECK (applied IN (0,1))
);
CREATE TABLE IF NOT EXISTS feed_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  received_at INTEGER NOT NULL,
  channel TEXT NOT NULL,
  state TEXT NOT NULL,
  detail TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS observations_symbol_kind_time ON observations(symbol,kind,source_time);
CREATE INDEX IF NOT EXISTS observations_identity ON observations(logical_id,id DESC);
CREATE INDEX IF NOT EXISTS receipts_observation ON receipts(observation_id,id);
PRAGMA user_version = 1;
