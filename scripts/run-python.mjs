import { spawn } from "node:child_process";
import { python } from "./python.mjs";
const child = spawn(python, process.argv.slice(2), {
  stdio: "inherit",
  env: process.env,
  detached: process.platform !== "win32",
});
let stopping = false;
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => {
    if (!stopping) {
      stopping = true;
      child.kill("SIGTERM");
    }
  });
child.on("exit", (code) => process.exit(code ?? 0));
child.on("error", (error) => {
  console.error(error.message);
  process.exit(1);
});
