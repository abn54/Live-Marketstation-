import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { python } from "./python.mjs";
if (existsSync(".env")) process.loadEnvFile(".env");
const apiPort = process.env.API_PORT ?? "8000";
const api = spawn(
  python,
  [
    "-m",
    "uvicorn",
    "server.main:create_app",
    "--factory",
    "--host",
    process.env.HOST ?? "127.0.0.1",
    "--port",
    apiPort,
  ],
  {
    stdio: "inherit",
    detached: process.platform !== "win32",
    env: { ...process.env, APP_ENV: "development" },
  },
);
const ui = spawn(
  process.execPath,
  ["node_modules/vite/bin/vite.js", "--port", process.env.PORT ?? "3000"],
  {
    stdio: "inherit",
    detached: process.platform !== "win32",
    env: { ...process.env, API_TARGET: `http://127.0.0.1:${apiPort}` },
  },
);
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  api.kill("SIGTERM");
  ui.kill("SIGTERM");
  process.exitCode = code;
}
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => stop());
for (const child of [api, ui]) {
  child.on("error", (error) => {
    console.error(error.message);
    stop(1);
  });
  child.on("exit", (code) => {
    if (!stopping) stop(code ?? 1);
  });
}
