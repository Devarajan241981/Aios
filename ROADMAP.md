# AIOS Roadmap

Honest, phased, and ordered by *what unlocks the most value per unit of solo
effort*. Each phase ends with something you can actually run and show.

The guiding principle: **build the AI OS experience on top of a working Linux
base, not underneath it.** We never touch the kernel until (and unless) a real
need forces it.

---

## Phase 1 — The AI core (✅ in progress, runs on macOS today)

The differentiator, buildable now with zero OS work.

- [x] `aiosd` loopback daemon with `/health` + `/v1/chat`
- [x] Pluggable backends: Ollama (OpenAI-compatible) + offline mock
- [x] Assistant orchestration with device-context grounding
- [x] `aios` CLI (`ask` / `chat` / `status`)
- [x] Offline test suite + CI
- [x] Streaming responses (token-by-token) over the HTTP API (SSE) + live CLI
- [x] Conversation persistence — named, resumable sessions in local SQLite
- [x] Hardening: bearer-token auth, structured logging, body limits, `/version`
- [x] Packaging: `pyproject.toml` + `aiosd` console entry point
- [x] Config file (`~/.config/aios/config.toml`, TOML) with defaults<file<env
      precedence, an `aios config` command, and a `/config` endpoint

**Exit criteria:** you use `aios` daily on your Mac for real questions.

## Phase 2 — Memory & semantic search (✅ core working)

Turn the assistant from stateless chat into something that knows *your* stuff.

- [x] Local document indexer (files, notes, markdown, code) → embeddings
- [x] Vector store with cosine search + JSON persistence (pure Python, no server)
- [x] Offline hashing embedder (zero downloads) + opt-in Ollama dense embedder
- [x] Retrieval step wired into the Assistant seam (RAG over your data)
- [x] "Where did I discuss X?" search (`aios search`) + `/v1/search` endpoint
- [ ] Incremental re-index (only changed files; mtime tracking)
- [ ] Explicit per-source permissions (assistant sees only what you allow)
- [ ] Encrypt the index at rest
- [ ] Upgrade to an ANN index (sqlite-vec / FAISS) if the corpus grows large

**Exit criteria:** ask about your own notes and get grounded answers, offline. ✅
(Basic version reached — dense-embedding quality + encryption still to come.)

## Phase 3 — The desktop shell (Linux target, ⏳ tooling ready)

Bring up AIOS as an actual desktop. This is where we move to hardware. The
bring-up tooling and a first shell are written and syntax-checked; running them
on the M4 is the remaining step (see [docs/asahi-bringup.md](docs/asahi-bringup.md)).

- [x] Compositor base chosen: **Sway/wlroots** (simplest, most stable)
- [x] Web UI as the shell (self-contained page served by `aiosd`)
- [x] Session tooling: `aios-session` (starts Sway) + `aios-shell` (kiosk browser)
- [x] Sway session config that autostarts `aiosd` and the shell
- [x] `aiosd` hardened systemd **user** service + `install.sh`/`uninstall.sh`
- [x] Login session entry (`aios.desktop`) + Asahi bring-up script
- [x] Global hotkey (`Super+Space`) → assistant overlay over other apps
      (Sway scratchpad + `aios overlay`, with its own persistent session)
- [x] Native panel (swaybar): backend health, index size, battery, clock, and a
      clickable AIOS button that summons the overlay (i3bar protocol)
- [ ] Boot Asahi Linux on the M4 and run the bring-up (needs hardware)
- [ ] App launcher + workspace switcher in the panel
- [ ] Theming (light/dark, accent) beyond the current web UI

**Exit criteria:** log into an AIOS session on the M4 and invoke the assistant
from anywhere.

## Phase 4 — System actions & automation (✅ core landed)

Let the assistant *do* things, safely. Shipped across Phase 2.5 / 2.6 (see
[ADR-0002](docs/decisions/0002-tools-safety.md)).

- [x] Tool/function-calling layer (assistant calls whitelisted capabilities)
- [x] Backend-agnostic agent loop (Ollama tool-calling + testable scripted path)
- [x] Sandboxed filesystem tools (home-confined, symlink-safe) + approval gate
- [x] Safe built-in tools: `current_time`, `system_info`, `list_dir`, `read_file`,
      `search_notes`
- [x] Preview-before-run gate with content-addressed approval
- [x] First mutating tools: `write_file`, `run_command` (allowlisted, no shell)
- [x] Interactive CLI approval loop (`aios ask --tools`) + non-interactive `--approve`
- [x] Richer previews: unified diffs for `write_file` overwrites, colored in the
      CLI and the web-UI approval card
- [x] Tool-invocation audit log (JSONL) with `aios audit` and a `/v1/audit` endpoint
- [ ] Trash-based delete/move tools behind the same gate
- [ ] Natural-language automations → scheduled jobs (systemd timers)
- [ ] Per-tool / per-session permission scopes

## Phase 5 — Distribution & polish

- [ ] Voice input (offline ASR: Vosk / whisper.cpp) → assistant
- [ ] Flatpak packaging for AIOS apps
- [ ] Installable image / setup script for the M4
- [ ] Docs site + demo video

---

## Reality checklist (things we will *not* pretend are easy)

- **Apple GPU acceleration on Asahi** is still maturing. Plan for a period of
  software rendering / limited GPU on the M4. Don't block Phase 3 on it.
- **Model size vs RAM.** A MacBook Air M4 comfortably runs 3B–8B quantized
  models. Bigger models need more RAM/patience. Default to small models.
- **"AI writes the OS" is a tool, not a plan.** ChatGPT/Claude accelerate coding;
  they don't remove the need to understand Wayland, systemd, and the model stack.
- **Correction to the original research doc:** Apple Silicon (M1–M4) SoCs do
  **not** contain a T2 chip — the T2 was a separate coprocessor on Intel Macs.
  The Secure Enclave and related functions are integrated into the M-series SoC
  itself. See [docs/architecture.md](docs/architecture.md).
