# AIOS Architecture

> **North star:** evolve from a Linux-hosted foundation into an increasingly
> independent operating system over many years — **usable at every stage** —
> by owning every interface and keeping every dependency replaceable.

AIOS is not "another Linux distribution." Linux is a **temporary hardware layer**
below two boundaries we own. Everything between them is AIOS.

## Read in this order

1. **[Engineering Constitution](00-engineering-constitution.md)** — the
   non-negotiable rules (layering, replaceability, anti-dead-end, quality,
   capability security). Start here.
2. **[Layered Architecture](01-layered-architecture.md)** — the layer stack, the
   two boundaries (HAL below, Platform API above), and Stages 1/2/3.
3. **[Dependency Replacement Matrix](02-dependency-replacement-matrix.md)** —
   every dependency, its isolating seam, replacement difficulty, and future.
4. **[Kernel Design & AKI](03-kernel-design.md)** — the eventual kernel, designed
   now (not built), and the interface that keeps Linux swappable.
5. **[Platform API v1](04-platform-api-v1.md)** — the frozen app-facing contract
   and its stability policy.

Decision records: [0003](../decisions/0003-layered-architecture-and-hal.md)
(layered architecture & HAL), [0004](../decisions/0004-eventual-kernel-and-aki.md)
(eventual kernel & AKI), [0005](../decisions/0005-service-manager-seam.md)
(ServiceManager seam), [0006](../decisions/0006-session-store-seam.md)
(SessionStore seam), [0007](../decisions/0007-freeze-platform-api-v1.md)
(freeze Platform API v1), [0008](../decisions/0008-transport-seam.md)
(Transport seam), [0009](../decisions/0009-inference-seam.md)
(inference seam), [0010](../decisions/0010-notification-center.md)
(notification center), [0011](../decisions/0011-update-manager-seam.md)
(UpdateManager seam), [0012](../decisions/0012-package-manager-seam.md)
(PackageManager seam), [0013](../decisions/0013-session-manager-seam.md)
(SessionManager seam). Earlier:
[0001](../decisions/0001-scope-and-strategy.md),
[0002](../decisions/0002-tools-safety.md).

## The two boundaries, in one picture

```
Applications
   ↓  AIOS PLATFORM API   (aiosd service API — apps target this; no Linux knowledge)
AIOS desktop + system services   (the AI runtime, tools, memory, shell — OURS)
   ↓  AIOS PLATFORM HAL   (aiosd/platform — isolates the host OS)
   ↓  AIOS KERNEL INTERFACE (AKI)   (isolates the kernel)
Linux (Asahi)  →  future: AIOS kernel
Hardware (Apple Silicon)
```

## Where the architecture already lives in code

| Principle | In the codebase today |
|-----------|-----------------------|
| HAL isolates the host | `ai-core/aiosd/platform/` (`Platform` + `PosixPlatform`); `context.py` has no OS code |
| App API is OS-agnostic | `aiosd/server.py` — the web UI and `aios` CLI are pure API clients |
| Everything behind an interface | `Backend`, `Embedder`, `VectorStore`, `Storage`, `Tool`, `Scheduler` |
| Capability security, top-down | tool preview-before-run + per-session grants + audit → mirror the kernel capability model |

## The rule for every dependency (Constitution §II.4)

Answer the **Four Questions** and add a matrix row: *why we use it · which
abstraction isolates it · how hard to replace · what replaces it.*
