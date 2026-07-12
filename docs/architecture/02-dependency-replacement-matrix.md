# Dependency Replacement Matrix

Every external dependency AIOS relies on, the AIOS interface that isolates it,
how hard it is to replace, and what replaces it. This table is **mandatory to
update** when adopting or removing a dependency (Constitution §II.4).

**Difficulty:** Trivial · Low · Medium · High · Extreme.
**Status:** ✅ ours today · 🟡 partly ours / behind our seam · ⬜ external, isolated.

## The independence chain

```
Hardware → [AKI] → Kernel(Linux) → [HAL] → System services (AIOS) → [Platform API] → Desktop (AIOS) → Apps
                    replaceable            OURS                       OURS               OURS
```

## Matrix

| # | Component | Why we use it | Isolating interface (the seam) | Current | Difficulty | Future implementation | Stage |
|---|-----------|---------------|-------------------------------|---------|-----------|----------------------|-------|
| 1 | **App platform API** | The contract apps target | **`aiosd` service API** (ours) — [v1 spec](04-platform-api-v1.md) | ✅ ours, **v1 frozen** | — | `/v2` only for a breaking change | 1 |
| 2 | **AI runtime / agent** | The core product | `Assistant`, `Agent`, `Registry` (ours) | ✅ ours | — | AIOS inference runtime | 1–2 |
| 3 | Model inference | Don't own a trained-model runtime yet | `Backend` interface | 🟡 Ollama / llama.cpp / mock | Low | AIOS inference engine (llama.cpp as lib → own) | 2 |
| 4 | Embeddings | Vector search | `Embedder` interface | ✅ hashing (ours) + 🟡 Ollama | Low | AIOS embedder | 1–2 |
| 5 | Vector store | Semantic memory | `VectorStore` interface | ✅ ours (pure Python) | Trivial | AIOS ANN engine | 2 |
| 6 | Persistence | Sessions/messages/grants | **`SessionStore` interface** (ours) — `aiosd/storage.py` | 🟡 `SqliteStore` behind it (only class that knows SQLite) | Low | AIOS store (keep SQLite unless it blocks us) | 2 |
| 7 | Config | Settings | `Config` + `load_config` (ours) | ✅ ours (TOML/env) | — | AIOS settings service | 1–2 |
| 8 | Tools / capabilities | Let the AI act, safely | `Tool`, capability/approval model (ours) | ✅ ours | — | AIOS capability system (kernel-aligned) | 1 |
| 9 | Audit | Trust/observability | `AuditLog` (ours) | ✅ ours | — | AIOS audit service | 1 |
| 10 | **Device/power facts** | Grounding | **`Platform` HAL** (ours) | 🟡 PosixPlatform | Low | AIOS-kernel Platform impl | 1/3 |
| 11 | Scheduling (automations) | Timed prompts | `Scheduler` (ours, AIOS-neutral) → `ServiceManager` | ✅ policy ours; 🟡 systemd timers behind the seam | Low | AIOS scheduler over `aiosinit` | 2 |
| 12 | Init / service manager | Start/supervise services & jobs | **`ServiceManager` interface** (ours) — `aiosd/platform/services.py` | 🟡 `SystemdServiceManager` (the only class that knows systemd) | Medium | `aiosinit` `ServiceManager` impl | 2 |
| 13 | Shell (CLI) | Human/automation entry | `aios` (ours) | ✅ ours (+ bash for scripts) | Low | AIOS shell | 1–2 |
| 14 | Desktop shell (panel/overlay/launcher) | The UX identity | shell components (ours) | 🟡 swaybar/web/scripts | Low–Med | native AIOS shell | 2 |
| 15 | Compositor / WM | Draw & manage windows | `Compositor` seam + AIOS shell protocol | ⬜ Sway (wlroots) | High | AIOS compositor (wlroots-as-lib → own) | 2–3 |
| 16 | Session / login | Start a user session | `SessionManager` seam *(to define)* | ⬜ greetd/DM + `aios-session` | Medium | AIOS greeter | 2 |
| 17 | UI toolkit | Build interfaces | AIOS UI / SDK | 🟡 web (HTML/CSS, ours) | Medium | AIOS UI toolkit | 2 |
| 18 | Notification center | System messaging | `Notifications` seam *(to define)* | ⬜ none/libnotify | Low | AIOS notification service | 2 |
| 19 | Package manager | Install software | `PackageManager` seam *(to define)* | ⬜ Flatpak/dnf | High | AIOS packages | 2 |
| 20 | Update system | Ship updates | `UpdateManager` seam *(to define)* | ⬜ dnf/ostree | Medium | AIOS atomic updates | 2 |
| 21 | File manager | Browse files | app over Platform API | ⬜ none | Low | AIOS file manager | 2 |
| 22 | Developer SDK | Third-party apps | AIOS SDK (over Platform API) | 🟡 the API exists | Medium | AIOS SDK + language bindings | 2 |
| 23 | IPC transport | Service ↔ app | **`Transport` interface** (ours) — `aiosd/transport.py` | 🟡 TCP-HTTP **+ Unix-socket-HTTP** behind it | Medium | AIOS IPC (message ports) | 2–3 |
| 24 | **Kernel** | Hardware, processes, VM | **AKI** (ours) | ⬜ Linux (Asahi) | Extreme | AIOS capability microkernel | 3 |
| 25 | Bootloader | Bring-up | boot protocol | ⬜ m1n1/U-Boot (open) | High | keep m1n1 / AIOS boot | 3 |
| 26 | Filesystem | Storage on disk | VFS (via AKI) | ⬜ btrfs/ext4 | Extreme | keep btrfs *or* AIOS FS (maybe never) | 3 |
| 27 | libc / runtime | Language runtime | language/runtime seam | ⬜ glibc + CPython | High | AIOS runtime (long-term) | 3 |
| 28 | GPU / graphics | Accelerated display | graphics stack (via AKI) | ⬜ Asahi Mesa | Extreme | AIOS graphics architecture | 3 |

## Reading the matrix

- Rows **1, 2, 5, 7, 8, 9, 13** are already ours — the value core of "MY OS."
- Rows marked **⬜ + "seam to define"** are honest debts: the dependency is used
  but its isolating interface isn't formalized yet. Formalizing each is a Stage-2
  task and each becomes an ADR.
- Rows **24–28 (Extreme)** are Stage-3 and deliberately last. Their *value today*
  is that the AKI/HAL keep them swappable — not that we rush to reimplement them.
- Difficulty is about **replacement**, assuming the seam holds. If replacing a
  dependency would require changes *above* its seam, that is a Constitution §II.5
  bug to fix first.
