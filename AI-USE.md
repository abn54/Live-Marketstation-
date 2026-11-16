# AI and tool disclosure — Assignment 4, Parts 4.1–4.2

## Coding agent and model

OpenAI Codex desktop was used as the coding agent in this chat to generate and revise source code, tests, startup scripts, documentation, report text, and demonstration tooling; run commands; inspect primary documentation; exercise the local app in a browser; and commit/push the authorized work to GitHub. The environment describes the coding agent as based on the GPT-6 family. The exact deployed model identifier/build was not exposed in the available session metadata and is not asserted here. No model switch was requested or recorded. No subagents were used.

The student's instructions supplied the Part 4.1 requirements, repository destination, and later the full overview. The agent performed the implementation and verification steps recorded here. This disclosure does not assert that the student independently authored, inspected, or mastered every generated line; the student must review and be able to explain the submitted code before presenting it.

## Tools and their roles

| Tool | Actual use |
| --- | --- |
| Codex workspace editor, terminal, and Git | Created/edited files, installed pinned dependencies, ran Python/Node commands, inspected SQLite, built/tested the app, and published commits. No separate VS Code or other editor was used by the agent for this work. |
| Codex browser automation | Exercised the actual localhost app, inspected visible status/ledger/replay/chart behavior, checked console logs, and captured screenshots for UI verification and the earlier generated demo. University authentication/restricted pages were not bypassed. |
| Web lookup and primary documentation | Checked Vue, FastAPI WebSockets, Yahoo/yfinance transport/protocol, and TradingView chart usage. The assignment overview was ultimately supplied as pasted text by the user. |
| pytest, FastAPI TestClient, httpx MockTransport, local WebSocket clients | Deterministic tests without external Yahoo traffic; injected values and failures are identified as test fixtures. |
| yfinance pricing protobuf + websockets + httpx | Decoded actual Yahoo pricing messages and fetched real chart OHLCV. They are data/transport libraries, not AI models. |
| Vue 3, Vite, vue-tsc, Lightweight Charts, Lucide Vue | Implemented/rendered/typechecked the frontend. Python FastAPI and sqlite3 implement the backend and storage. Node is used for frontend tooling, launchers, and an independent evidence client. |
| Prettier and Black | Formatted generated TypeScript/Vue/JavaScript and Python for review. |
| macOS `say` (Samantha voice) and FFmpeg | Previously generated a narrated demo from UI captures. The user chose to record their own video. The generated media and assembler were withdrawn. |
| GitHub Actions | Configured repeatable Python tests and Vue build checks on pushes and pull requests. Local clean-checkout results and observed remote CI status are distinguished in verification notes. |

## Part 4.2 work on November 15

Codex implemented the SMA overlays and crossover markers, receipt-driven paper account, persistent simulation snapshots, backtest controls, tests, offline evidence, and documentation. Defaults of 9/21 bars, $10,000 cash, 95% allocation, 10 bps fees and 5 bps slippage were implementation choices, with editable controls and explicit assumptions. The agent used pandas as an independent rolling-mean reference and Node to run the Vue calculator in the Python verification tests. It used FFmpeg to edit the student's recordings for Parts 4.1 and 4.2.

The Sites skill supplied local development and browser-verification guidance. The implementation uses the existing Vue/FastAPI checkout. Codex used primary pandas and TradingView documentation for calculation and execution-timing references, Black and Prettier for touched source files, and the supported browser tool for verification. The first Vue build exposed a marker generic-type mismatch, which was corrected with the chart library's `Time` type. Browser testing exposed slow joins on the larger market history, leading to the `heads_observation` index. These changes and their verification are recorded in the evidence log. No subagents were used.

## Revised choices and why

The first implementation used React/Express because the initial Part 4.1 excerpt did not state a framework requirement and the linked full overview was behind university authentication. After the user pasted the overview's explicit **Vue frontend, FastAPI backend, SQLite on localhost** requirement, the agent migrated the implementation to Vue 3 and Python FastAPI. The existing SQLite schema and immutable observations were preserved. This is a revised implementation approach, not a model/provider switch. The original code remains identifiable in Git history; it is not the submitted implementation.

Python's initial WebSocket TLS handshake failed because its default certificate store could not find a trusted issuer. The revision supplies certifi's trusted CA roots while retaining hostname and certificate verification. Tests check those protections, and live evidence separately confirms real Yahoo messages arrive. The code does not disable TLS verification.

The first Python test pass exposed WebSocket shutdown cancellation and a test that expected retry status before asynchronous cleanup finished. Endpoint cleanup now handles cancellation explicitly, and the test waits for the actual retry event. The curated log links the failure, changed code, passing tests, and remaining limits.

## AI features in the submitted product

Part 4.1 does not call an AI decision model, chatbot, vision model, or live-audio AI service. No OpenAI API key or other model-provider credentials are required or transmitted by this application. Those features belong to later parts and have not been implemented or claimed here. Market observations come from Yahoo Finance; replay comes from recorded SQLite observations, not model-generated prices.

Codex used the browser to rehearse the recording flow after the student reported trouble. Codex changed the Vue layout and chart view, added the SQLite replay checkpoint and FastAPI route, corrected per-connection quote freshness, and added regression coverage. The student supplies the spoken recording.

## Evidence and redaction

[Curated evidence log](docs/evidence-log.md), [verification](docs/verification.md), and the report connect selected requirements/prompts to generated artifacts, checks, and decisions. Full chat exports, credentials, personal filesystem details, authentication data, and private third-party browser content are excluded. GitHub's existing commit identity and the requested public repository identify the submission; screenshots and recordings contain the local application and public market data.

## Student-recorded video preference

The student recorded and narrated both demonstrations in Kaltura. Codex prepared private recording notes and used Kaltura transcripts and FFmpeg to select and trim scenes. The Part 4.1 clip lasts 58.92 seconds. The Part 4.2 clip lasts 59.12 seconds and uses five chronological excerpts, retaining the student's narration at its original speed. Browser chrome and the desktop dock were cropped, and audio gain and short cut-edge fades improved playback. The report links the Part 4.2 clip.
