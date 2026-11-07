"""Verify a fresh local Git clone without borrowing ignored runtime state.

Run with the project's Python after committing the candidate source:
    .venv/bin/python -m scripts.verify_clean_checkout
This checks installation/build/test, genuine recording import, and an actual
production FastAPI HTTP/WebSocket server. It does not claim live Yahoo evidence;
that is captured separately by npm run evidence.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import httpx
from websockets.asyncio.client import connect

repo = Path(__file__).resolve().parent.parent
sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
started = time.time()
result = {
    "sourceCommit": sha,
    "method": "fresh git clone --no-local; no ignored runtime files copied",
    "checks": [],
    "liveYahooClaim": False,
}
with tempfile.TemporaryDirectory(prefix="marketstation-clean-") as task_tmp:
    checkout = Path(task_tmp) / "checkout"

    def redact(text):
        for private, alias in [
            (str(checkout), "<clean-checkout>"),
            (str(repo), "<workspace>"),
            (task_tmp, "<temporary-dir>"),
            (str(Path.home()), "<user-home>"),
        ]:
            text = text.replace(private, alias)
        return text

    def run(args, env=None):
        mark = time.time()
        p = subprocess.run(
            args,
            cwd=checkout if checkout.exists() else repo,
            env=env,
            capture_output=True,
            text=True,
        )
        entry = {
            "command": [redact(str(a)) for a in args],
            "exitCode": p.returncode,
            "seconds": round(time.time() - mark, 2),
            "outputTail": redact((p.stdout + p.stderr)[-4500:]),
        }
        result["checks"].append(entry)
        if p.returncode:
            raise RuntimeError(entry["outputTail"])
        return p.stdout

    try:
        run(["git", "clone", "--quiet", "--no-local", str(repo), str(checkout)])
        run(["git", "checkout", "--quiet", sha])
        ignored = [".venv", "node_modules", ".env", "dist", "data/market.sqlite"]
        result["initiallyAbsent"] = {
            path: not (checkout / path).exists() for path in ignored
        }
        assert all(result["initiallyAbsent"].values())
        run([sys._base_executable, "-m", "venv", ".venv"])
        python = checkout / (
            ".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python"
        )
        run([str(python), "-m", "pip", "install", "--quiet", "-r", "requirements.txt"])
        run(["npm", "ci", "--no-fund", "--no-audit"])
        run(["npm", "test"])
        run(["npm", "run", "build"])
        env = dict(
            os.environ,
            DATABASE_PATH=str(checkout / "data/clean.sqlite"),
            ENABLE_DEMO_CONTROLS="false",
        )
        run(["npm", "run", "db:init"], env)
        run(["npm", "run", "recording:import"], env)
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            port = reserved.getsockname()[1]
        env["PORT"] = str(port)
        log = Path(task_tmp) / "server.log"
        with log.open("w") as output:
            process = subprocess.Popen(
                ["npm", "start"],
                cwd=checkout,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                base = f"http://127.0.0.1:{port}"
                with httpx.Client(timeout=2) as client:
                    health = None
                    for _ in range(100):
                        if process.poll() is not None:
                            raise RuntimeError(redact(log.read_text()))
                        try:
                            response = client.get(base + "/api/health")
                            if response.status_code == 200:
                                health = response.json()
                                break
                        except httpx.HTTPError:
                            pass
                        time.sleep(0.1)
                    assert health and health["stack"] == {
                        "frontend": "Vue 3",
                        "backend": "FastAPI",
                        "database": "SQLite",
                    }
                    page = client.get(base + "/")
                    assert page.status_code == 200 and "/assets/" in page.text
                    bars = client.get(base + "/api/candles?symbol=BTC-USD").json()
                    assert bars["candles"]
                    replay = client.get(
                        base + "/api/replay?symbol=BTC-USD&limit=1"
                    ).json()
                    assert replay["mode"] == "recorded" and replay["records"]
                    assert (
                        client.post(
                            base + "/api/demo/feed", json={"action": "disconnect"}
                        ).status_code
                        == 403
                    )

                async def probe():
                    async with connect(f"ws://127.0.0.1:{port}/ws", origin=base) as ws:
                        snapshot = json.loads(await asyncio.wait_for(ws.recv(), 5))
                        assert (
                            snapshot["type"] == "snapshot"
                            and len(snapshot["symbols"]) == 4
                        )
                        return {
                            "type": snapshot["type"],
                            "symbols": len(snapshot["symbols"]),
                            "persistedObservations": snapshot["stats"]["observations"],
                        }

                result["productionSmoke"] = {
                    "http200": True,
                    "stack": health["stack"],
                    "candlesAvailable": len(bars["candles"]),
                    "recordedReplayAvailable": True,
                    "demoControlsDisabled": True,
                    "webSocket": asyncio.run(probe()),
                }
            finally:
                # Send one signal to the launcher; it forwards to its detached
                # Python child and waits for graceful SQLite/feed shutdown.
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise RuntimeError("Clean server did not shut down")
        result["passed"] = True
    except BaseException as exc:
        result["passed"] = False
        result["failure"] = redact(str(exc))
        raise
    finally:
        result["seconds"] = round(time.time() - started, 2)
        (repo / "evidence/clean-checkout.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
print(
    json.dumps(
        {
            "passed": result["passed"],
            "sourceCommit": sha,
            "seconds": result["seconds"],
            "checks": len(result["checks"]),
        }
    )
)
