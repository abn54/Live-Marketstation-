import { existsSync } from "node:fs";
import { resolve } from "node:path";
export const python = resolve(
  process.platform === "win32"
    ? ".venv/Scripts/python.exe"
    : ".venv/bin/python",
);
if (!existsSync(python)) {
  throw new Error(
    "Create the Python environment first: python3 -m venv .venv, then .venv/bin/python -m pip install -r requirements.txt (Windows: .venv\\Scripts\\python.exe).",
  );
}
