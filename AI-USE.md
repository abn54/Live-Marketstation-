# AI and tool disclosure — Assignment 4, Part 4.1

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
| macOS `say` (Samantha voice) and FFmpeg | Previously generated a narrated demo from UI captures. The user declined that generated video/narration and requested a speaking script for their own recording. Those media files and the assembler are removed from the current tree; the historical tool use remains disclosed. |
| GitHub Actions | Configured repeatable Python tests and Vue build checks on pushes and pull requests. Local clean-checkout results and observed remote CI status are distinguished in verification notes. |

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

The user requested removal of the generated demo/narration and a rubric-aligned script they will speak themselves. The current tree therefore contains [a speaking script](docs/part-4-1-speaking-script.md), not a completed replacement video. The report is awaiting the student's actual accessible 30–60 second recording link. No student voice recording has been created or claimed by the agent. Normal Git history still identifies the withdrawn earlier artifacts; history was not rewritten.
