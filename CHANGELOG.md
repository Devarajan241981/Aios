# Changelog

## v0.3.0 — 2026-07-12

First tagged release of **AIOS**, a privacy-first, local AI operating-system
layer. Standard-library only (no third-party dependencies); 138 tests, all
passing; everything runs on-device with no data leaving the machine.

### AI core
- `aiosd` loopback daemon: `/health`, `/version`, `/config`, `/v1/chat`
  (JSON and SSE token-by-token streaming).
- Backends: **Ollama** (OpenAI-compatible; also works with llama.cpp-server /
  LocalAI) and an offline **mock** backend for tests/demos.
- Assistant with device-context grounding.

### Semantic memory
- Pure-Python hashing embedder (zero downloads) + opt-in Ollama dense embeddings.
- Local vector store + filesystem indexer; retrieval-augmented answers.
- `aios index` / `aios search`.

### Sessions & agent
- SQLite persistence: named, resumable chat sessions (`aios sessions` / `history`).
- Backend-agnostic tool-calling agent loop; sandboxed **read** tools
  (`current_time`, `system_info`, `list_dir`, `read_file`, `search_notes`).
- **Mutating** tools (`write_file`, `run_command`, `move_file`,
  `delete_file`→trash) behind **preview-before-run** with content-addressed
  approval and colored unified diffs.
- Tool-invocation **audit log** (`aios audit`, `/v1/audit`).

### Interfaces
- Self-contained **web UI** served at `/` (chat, streaming, sessions,
  tool-approval dialog with diffs; light/dark).
- CLI: `ask` / `chat` / `overlay` / `index` / `search` / `sessions` / `history`
  / `tools` / `audit` / `config` / `doctor` / `status`.
- `aios doctor` one-command setup diagnostics.

### Desktop (Apple Silicon / Asahi Linux)
- Session bring-up: `aios-session`, `aios-shell`, Sway config, login entry.
- Global-hotkey assistant **overlay** (`Super+Space`).
- Native **panel** (swaybar status) and app **launcher** (`Super+D`).
- `install.sh` / `uninstall.sh` / `asahi-bringup.sh`.

### Hardening & configuration
- Optional bearer-token auth, structured logging, request body-size limits.
- **TOML config** (`~/.config/aios/config.toml`) with precedence
  defaults < file < environment.
