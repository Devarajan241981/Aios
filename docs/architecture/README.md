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

Decision records: [ADR-0003](../decisions/0003-layered-architecture-and-hal.md)
(layered architecture & HAL), [ADR-0004](../decisions/0004-eventual-kernel-and-aki.md)
(eventual kernel & AKI). Earlier: [ADR-0001](../decisions/0001-scope-and-strategy.md),
[ADR-0002](../decisions/0002-tools-safety.md).

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
