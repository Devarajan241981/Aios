# AIOS — a privacy-first, local AI operating system

[![CI](https://github.com/Devarajan241981/Aios/actions/workflows/ci.yml/badge.svg)](https://github.com/Devarajan241981/Aios/actions/workflows/ci.yml)

AIOS is an AI-native desktop environment where an on-device assistant is a
first-class part of the OS, not a bolt-on app. Everything runs **locally by
default** — no telemetry, no cloud round-trips, your data never leaves the
machine.

> **What AIOS actually is (and isn't).** AIOS is **not** a new kernel and not a
> fork of the Linux kernel. Writing a kernel is out of scope for a solo
> project — and unnecessary. AIOS is an **AI-integrated desktop layer** that
> runs on top of an existing Linux base (target: [Asahi Linux](https://asahilinux.org/)
> on Apple Silicon). The part that makes it *AIOS* is the AI core, the desktop
> shell, and how they're wired into the system. That is what this repo builds.

## Status

**Phase 1 — the AI core — is running today, on macOS, on your Mac.** No Linux,
no kernel work, no cloud. The rest is on the [roadmap](ROADMAP.md).

| Component | State |
| --- | --- |
| `aiosd` — local assistant daemon (HTTP, loopback) | ✅ working, tested |
| **Web UI** — self-contained chat app served by the daemon | ✅ working, tested |
| `aios` — CLI (`ask`/`chat`/`overlay`/`index`/`search`/`sessions`/`tools`/`audit`/`config`/`doctor`/…) | ✅ working |
| **`aios doctor`** — one-command setup diagnostics | ✅ working, tested |
| **Global-hotkey overlay** (`Super+Space`) — assistant over any app (Sway) | ✅ working, tested |
| **Native panel** (swaybar): backend health, index size, battery, clock, AIOS button | ✅ working, tested |
| Streaming replies (token-by-token, SSE) — daemon + live CLI | ✅ working, tested |
| Ollama backend (+ OpenAI-compatible, works with llama.cpp / LocalAI) | ✅ working |
| Offline mock backend (for tests & demos) | ✅ working |
| Device-context grounding | ✅ basic (time, host, OS, battery) |
| Semantic search over your files (index + retrieval) | ✅ working, tested |
| Offline hashing embedder (zero-download) + Ollama embedder | ✅ working |
| RAG: assistant answers grounded in your indexed files | ✅ working |
| **Persistent chat sessions** (SQLite, resume across restarts) | ✅ working, tested |
| **Tool use / agent loop** (sandboxed read tools, backend-agnostic) | ✅ working, tested |
| **Mutating tools** (`write_file`, `run_command`, `move_file`, `delete_file`→trash) with preview-before-run | ✅ working, tested |
| **Hardening**: bearer-token auth, structured logging, body limits, `/version` | ✅ working, tested |
| **Audit log** — every tool run + approval recorded (JSONL), `aios audit` | ✅ working, tested |
| Wayland desktop shell on Asahi | ⏳ planned (Phase 3) |

## Quick start (2 minutes)

```bash
# 1. See it work right now with zero setup (offline mock backend):
make mock          # in one terminal — starts the daemon
open http://127.0.0.1:8765/   # ← the web UI: chat, sessions, tool approvals
make status        # or from another terminal: {"status": "ok", ...}
./bin/aios ask "hello"      # -> [mock:llama3.2] hello

# 2. Real local LLM via Ollama:
ollama serve                 # start Ollama (installed at /opt/homebrew/bin)
ollama pull llama3.2         # download a small local model (~2 GB)
make run                     # start aiosd with the real backend
./bin/aios ask "how do I free up disk space on macOS?"
./bin/aios chat              # interactive session

# 3. Semantic memory over your own files (offline, no downloads):
./bin/aios index ~/Documents ~/notes   # build a local index of your text/markdown/code
./bin/aios index --stats               # see what's indexed
./bin/aios search "where did I discuss the Q3 budget?"
# ...and `ask`/`chat` now answer grounded in those files, citing the source path.
```

Semantic search uses a pure-Python hashing embedder by default (zero downloads).
For higher-quality results, opt into local dense embeddings:
`AIOS_EMBEDDINGS=ollama AIOS_EMBED_MODEL=nomic-embed-text` (run `ollama pull nomic-embed-text` first).

```bash
# 4. Persistent, resumable conversations (stored locally in SQLite):
./bin/aios chat --session work    # everything in this session is remembered
./bin/aios sessions               # list saved sessions
./bin/aios history work           # replay a transcript

# 5. Let the assistant act on your machine via sandboxed tools:
./bin/aios tools                  # list available tools
./bin/aios ask --tools "what's in my Downloads folder, and what time is it?"

# Mutating actions are previewed and require your approval:
./bin/aios ask --tools "write a haiku to ~/notes/haiku.txt"
#   → shows exactly what it will write, waits for [y/N]
./bin/aios ask --tools --approve "…"   # non-interactive: auto-approve
```

**Tools are sandboxed and safe-by-default.** Read tools (`list_dir`, `read_file`,
`system_info`, `current_time`, `search_notes`) run automatically but filesystem
access is confined to your home (plus `AIOS_ALLOWED_ROOTS`) with symlink-safe
path checks. **Mutating tools** (`write_file`, `run_command`) use *preview-before-run*:
the daemon halts and shows you the exact effect — a **colored unified diff** when
`write_file` would overwrite an existing file — and executes **only** the action
you approve, verified by a content hash, so you never run something different
from what you saw. `run_command` is additionally restricted to an allowlist
(`AIOS_ALLOWED_COMMANDS`). Full model: [docs/decisions/0002-tools-safety.md](docs/decisions/0002-tools-safety.md).

To avoid re-approving within a trusted conversation, grant a tool to a session:
`aios grant <session> write_file` (or "Always allow" in the web-UI approval
dialog); revoke with `aios revoke <session> write_file`.

Not sure what's set up? Diagnose everything in one command:

```bash
./bin/aios doctor   # checks daemon, backend, model, index, tools, PATH, Ollama…
```

Run the tests (fully offline, no Ollama required):

```bash
make test
```

## How it fits together

```
  you ──▶ aios (CLI)  ─┐
                       ├─HTTP▶  aiosd  ──▶ Assistant ──▶ Backend ──▶ local LLM
  desktop UI ─────────┘        (127.0.0.1)   │                       (Ollama / llama.cpp)
                                             └─ device context (time, host, battery, …)
```

- **`aiosd`** is a small daemon that binds to loopback only and exposes
  `POST /v1/chat` and `GET /health`.
- The **Assistant** injects the AIOS persona + live device context, then calls a
  pluggable **Backend**.
- **Backends**: `ollama` (default, talks to any OpenAI-compatible local server)
  and `mock` (deterministic, offline — powers the tests).

See [docs/architecture.md](docs/architecture.md) for the full picture and
[docs/decisions/0001-scope-and-strategy.md](docs/decisions/0001-scope-and-strategy.md)
for *why* it's built this way.

## Configuration

Settings resolve as **defaults < `~/.config/aios/config.toml` < environment
variables**. Copy [docs/config.example.toml](docs/config.example.toml) to
`~/.config/aios/config.toml` to make settings persistent (TOML keys mirror the
env vars, lowercased, without the `AIOS_` prefix). Run `aios config` to see the
file path and the daemon's effective settings.

Every setting is also an environment variable (local-first defaults):

| Variable | Default | Meaning |
| --- | --- | --- |
| `AIOS_HOST` | `127.0.0.1` | bind address (keep on loopback) |
| `AIOS_PORT` | `8765` | daemon port |
| `AIOS_BACKEND` | `ollama` | `ollama` or `mock` |
| `AIOS_MODEL` | `llama3.2` | model name passed to the backend |
| `AIOS_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama endpoint |
| `AIOS_TIMEOUT` | `120` | per-request timeout (seconds) |
| `AIOS_EMBEDDINGS` | `hashing` | `hashing` (offline) or `ollama` |
| `AIOS_EMBED_MODEL` | `nomic-embed-text` | embedding model (Ollama backend) |
| `AIOS_INDEX_PATH` | `~/.local/share/aios/index.json` | where the vector index is stored |
| `AIOS_RAG` | `on` | ground chat replies in indexed files |
| `AIOS_RAG_TOPK` | `4` | excerpts retrieved per query |
| `AIOS_DB_PATH` | `~/.local/share/aios/aios.db` | SQLite conversation store |
| `AIOS_HISTORY_LIMIT` | `40` | max prior turns replayed from a session |
| `AIOS_TOOLS` | `on` | enable the tool/agent layer |
| `AIOS_ALLOWED_ROOTS` | *(home only)* | extra dirs tools may read/write (`:`-separated) |
| `AIOS_ALLOWED_COMMANDS` | *(safe default set)* | extra commands `run_command` may run |
| `AIOS_TOKEN` | *(none)* | if set, require `Authorization: Bearer <token>` |
| `AIOS_LOG_LEVEL` | `INFO` | daemon log level |
| `AIOS_MAX_BODY_BYTES` | `4000000` | reject request bodies larger than this |
| `AIOS_AUDIT` | `on` | record tool activity to an audit log |
| `AIOS_AUDIT_PATH` | `~/.local/share/aios/audit.log` | audit log location |
| `AIOS_TRASH_PATH` | `~/.local/share/aios/trash` | where `delete_file` moves files |

## Repository layout

```
ai-core/aiosd/     the daemon, organized by subsystem:
                     backends.py   model backends (Ollama, mock) + streaming + tools
                     assistant.py  prompt/context/RAG composition
                     embeddings.py store.py indexer.py retriever.py  — semantic memory
                     storage.py    SQLite session/message persistence
                     tools.py agent.py  — sandboxed tools + tool-calling loop
                     server.py     HTTP API, auth, logging, routing (AppState)
                     ui.py         self-contained web UI served at GET /
                     config.py context.py
ai-core/tests/     offline unittest suite (87 tests, mock backend)
ai-core/pyproject.toml   packaging (aiosd console script)
bin/aios           the CLI client
docs/              architecture + decision records (ADR-0001, ADR-0002) + Asahi bring-up
packaging/systemd/ hardened user service unit for the Linux target
packaging/desktop/ Sway session, aios-shell/aios-session, login-session entry
scripts/           install.sh / uninstall.sh / asahi-bringup.sh
.github/workflows/ CI (tests on Python 3.11–3.13)
```

## Running AIOS as a desktop (Apple Silicon / Asahi Linux)

Phase 3 turns a MacBook into an AIOS machine: `aiosd` runs as a systemd user
service and the web UI is the fullscreen shell under a minimal Sway session.

```bash
# on Fedora Asahi Remix, from a checkout of this repo:
./scripts/asahi-bringup.sh --dry-run    # preview every step
./scripts/asahi-bringup.sh              # install session deps + AIOS
# then log out and pick the "AIOS" session, or run: aios-session
```

The session has a top **panel** (swaybar) showing the AI backend's health, how
many documents are indexed, battery, and the clock — with an **AIOS button** you
can click to summon the assistant. And you can press **`Super+Space`** to summon
it as a small floating overlay over whatever you're doing (`Ctrl-D` hides it; it
keeps its own memory across summons). The overlay also works standalone in any
terminal: `aios overlay`. **`Super+D`** opens an app launcher (wofi/fuzzel/bemenu).

The bring-up scripts and session config are written and syntax-checked here; the
final run happens on the M4. Full guide: [docs/asahi-bringup.md](docs/asahi-bringup.md).

## License

MIT — see [LICENSE](LICENSE). All dependencies are stdlib-only.
