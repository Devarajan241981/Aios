# ADR 0003 — Layered architecture, the HAL, and the Platform API

- **Status:** accepted
- **Date:** 2026-07-12
- **Supersedes framing in:** [ADR-0001](0001-scope-and-strategy.md) (which
  established "AIOS is a layer on Linux"; this ADR makes that layer *independent
  and replaceable by design*).

## Context

The project's goal was raised from "a usable local AI desktop on Linux" to "an
operating system that evolves toward independence from Linux over 10+ years,
recognized as its own OS, usable at every stage." That demands an architecture
where **Linux is a temporary, replaceable hardware layer** and every user-facing
component can eventually be ours — without a big-bang rewrite and without
drowning in speculative abstraction.

## Decision

1. Adopt the **layered architecture** in
   [docs/architecture/01](../architecture/01-layered-architecture.md) with two
   AIOS-owned boundaries:
   - the **Platform API** (the `aiosd` service API) above the system services —
     the only thing applications may target;
   - the **Platform HAL** + **AKI** below the system services — the only path to
     host/kernel specifics.
2. Ratify the **[Engineering Constitution](../architecture/00-engineering-constitution.md)**
   as normative. Its prime directive: **own the interface; the third-party
   component is a swappable implementation behind it.**
3. Maintain the **[Dependency Replacement Matrix](../architecture/02-dependency-replacement-matrix.md)**;
   adopting/removing a dependency updates it and cites this ADR.
4. Implement the **first HAL boundary now** (`aiosd/platform/`) and refactor
   `context.py` to prove the pattern (no OS-specific code above the HAL).
5. Guard against **both** dead-ends: lock-in (Article 7) *and* over-abstraction
   (Article 8). Interfaces at proven seams; name future seams in docs until a
   real second implementation exists.

## Consequences

- Every future component decision is measured against the Constitution and the
  matrix. Reviews reject direct Linux/systemd/POSIX use above the HAL, and reject
  app code that bypasses the Platform API.
- Replacing an implementation touches one adapter, not the system.
- Some effort now goes to interfaces rather than features — accepted as the cost
  of a 10-year-maintainable, replaceable system (Article 14).

## Rejected alternatives

- **Ship fastest MVP, refactor for independence later.** Rejected: retrofitting
  boundaries after lock-in is the classic dead-end this project must avoid.
- **Abstract every dependency immediately behind multiple implementations.**
  Rejected: abstraction sludge; violates Article 8. We isolate at real seams and
  document the rest.
- **Fork a distro and rebrand.** Rejected: that is "another Linux distribution,"
  explicitly not the goal.
