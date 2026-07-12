# AIOS Layered Architecture & the Independence Path

This is the master architecture document. It defines the layers, the two
boundaries that make AIOS replaceable (the **HAL** below and the **Platform API**
above), and the staged plan to evolve from Linux-hosted to self-hosted.

## The layer stack

```
┌──────────────────────────────────────────────────────────────┐
│  Applications            (web UI, CLI, future native apps)     │
├──────────────────────────────────────────────────────────────┤
│  ══ AIOS PLATFORM API ══  the app-facing boundary (OURS)       │  ← apps target this
│     the aiosd service API: chat, memory, tools, sessions, …    │
├──────────────────────────────────────────────────────────────┤
│  Desktop layer           shell, panel, overlay, launcher,      │
│                          compositor seam, session/login seam   │
├──────────────────────────────────────────────────────────────┤
│  System services         AI runtime (aiosd), storage, index,   │
│                          audit, scheduler, update, packages    │
├──────────────────────────────────────────────────────────────┤
│  ══ AIOS PLATFORM HAL ══  the host boundary (OURS)             │  ← isolates the OS
│     device facts, power, services, fs roots, IPC transport     │
├──────────────────────────────────────────────────────────────┤
│  ══ AIOS KERNEL INTERFACE (AKI) ══  the kernel boundary (OURS) │  ← isolates the kernel
├──────────────────────────────────────────────────────────────┤
│  Kernel                  Linux (Asahi) today → AIOS kernel      │  ← swappable provider
├──────────────────────────────────────────────────────────────┤
│  Hardware                Apple Silicon (M-series), later more   │
└──────────────────────────────────────────────────────────────┘
```

Two boundaries do all the work of independence:

- **The Platform API (above the system services).** Applications are written
  against it and are forbidden (Constitution §I.3) from touching Linux/systemd/
  POSIX. Today this is the **`aiosd` HTTP/IPC API** — already OS-agnostic. Apps
  literally cannot tell which kernel exists. *This is the app-facing "syscall"
  layer of AIOS.*
- **The HAL + AKI (below the system services).** Everything OS/kernel-specific is
  reached only through these. Swapping Linux for our kernel means writing a new
  provider below this line; nothing above changes.

Everything between the two boundaries is **AIOS**. The kernel below and the apps
above both plug into interfaces we own.

## The HAL, concretely (this exists today)

`aiosd/platform/` defines the `Platform` interface; `PosixPlatform` implements it
for Linux (and macOS during development). `context.py` — the assistant's
device-grounding — was refactored to contain **zero** OS-specific code; it asks
the `Platform`. This is the pattern every host dependency follows:

> host-specific fact/action  →  a method on an AIOS interface  →  a per-OS
> implementation selected in exactly one place.

The HAL grows **by need, not by speculation** (Constitution §III.8): today it
covers device/power facts; it will grow to service management, filesystem roots,
and the IPC transport as those subsystems are pulled behind their seams.

## The Platform API, concretely (this exists today)

The `aiosd` daemon exposes a stable, loopback API (`/v1/chat`, `/v1/index`,
`/v1/search`, `/v1/sessions`, `/v1/tools`, `/v1/audit`, `/config`, …). The web UI
and the `aios` CLI are **applications** that use only this API. They have no
Linux knowledge. Native apps and the SDK will target the same surface. Freezing
and versioning this API (`Platform API v1`) is a Stage-1 deliverable.

## The stages

### Stage 1 — Linux as Hardware Abstraction Layer *(current)*
- Linux/Asahi provides only hardware access.
- The **HAL** and **Platform API** boundaries exist and are enforced.
- Everything between them that is practical to own, we own (AI runtime, memory,
  tools, sessions, audit, shell, CLI, web UI, panel, overlay, launcher).
- Exit criterion — **Platform API v1 frozen** ([04](04-platform-api-v1.md),
  ADR-0007) ✅; every dependency has a matrix row + isolating seam (in progress:
  HAL ✅, ServiceManager ✅, SessionStore ✅).

### Stage 2 — Own the userland, layer by layer
Replace, **behind existing interfaces**, in rough priority order (value ×
feasibility ÷ risk):
1. **Init / service manager** (systemd → `aiosinit` behind a `ServiceManager` seam)
2. **Shell & developer SDK** (extend `aios`; publish the SDK against Platform API)
3. **Notification center / control center** (new AIOS services, no legacy dep)
4. **Settings** (an AIOS settings service over the config subsystem)
5. **Package manager UI & update system** (behind `PackageManager`/`UpdateManager`)
6. **Compositor/window-manager seam** (own the *shell protocol*; keep wlroots as a
   library provider — see the challenge below)
7. **Session/login** (greetd → AIOS greeter behind `SessionManager`)
8. **File manager**
Each item lands only when its interface is stable and it beats the incumbent for
users or independence (Constitution "whether to replace").

### Stage 3 — The kernel becomes swappable, then (maybe) ours
- Define the **AIOS Kernel Interface (AKI)** now (done: see
  [03-kernel-design.md](03-kernel-design.md)). Linux is one AKI provider.
- Design the kernel from day one (also done — spec only, no implementation).
- If/when justified, implement an AKI provider on our own kernel. Because the
  boundary exists, this is an additive provider, not a rewrite.

## Architect's challenges (recorded, per your request to be challenged)

- **Do not write a Wayland compositor from scratch early.** It is multi-year and
  low-differentiation. Own the **shell and window-management *protocol/policy***
  (that is your identity); consume `wlroots` as a *library* provider behind a
  `Compositor` seam. Replace the library only if it blocks you.
- **Do not reimplement SQLite, ext4, or the C library for vanity.** These are
  mature, correct, and already behind (or easily behind) our interfaces. Effort
  spent here is effort not spent on the AI runtime and app platform — which are
  the actual "MY OS."
- **Freeze the Platform API early and guard it ferociously.** The single biggest
  long-term risk is app-facing API churn. Versioned, documented, tested.
- **The kernel is a boundary first.** Its value for years is that AKI keeps Linux
  swappable. Treat "write our kernel" as optional downstream of a healthy AKI,
  not as the goal.

## Related

- [00 — Engineering Constitution](00-engineering-constitution.md)
- [02 — Dependency Replacement Matrix](02-dependency-replacement-matrix.md)
- [03 — Kernel Design & AKI](03-kernel-design.md)
- ADR [0003](../decisions/0003-layered-architecture-and-hal.md),
  [0004](../decisions/0004-eventual-kernel-and-aki.md)
