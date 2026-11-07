import { existsSync } from "node:fs";
import { MarketStore } from "../server/store.js";
if (existsSync(".env")) process.loadEnvFile(".env");
const path = process.env.DATABASE_PATH ?? "./data/market.sqlite";
const store = new MarketStore(path);
console.log(`SQLite initialized: ${path}`);
console.log(store.stats());
store.close();
