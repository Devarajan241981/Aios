# ADR 0006 — The SessionStore seam (isolating SQLite)

- **Status:** accepted
- **Date:** 2026-07-12
- **Implements:** Constitution §II (replaceability); matrix row #6. Follows the
  seam pattern established in [ADR-0005](0005-service-manager-seam.md).

## Context

`storage.py` exposed a concrete `Storage` class bound to `sqlite3`, used directly
by the daemon. Persistence is a subsystem that must remain swappable (a future
AIOS store, an encrypted store, a networked store), so the concrete engine should
sit behind an AIOS-owned interface — not be the interface.

## Decision

Define **`SessionStore`** — the AIOS-owned persistence contract, expressed in
domain terms (sessions, messages, permission grants), with **no SQLite idioms**
crossing it. `SqliteStore` implements it and is the only class that knows SQLite.
Callers obtain an instance from **`open_store(config)`** (the single selection
point) and depend on the interface type.

### The Four Questions

1. **Why SQLite?** Stdlib, zero-dependency, correct, transactional, ideal for a
   local single-user store. No reason to build our own yet.
2. **Which abstraction isolates it?** `SessionStore` — domain methods only.
3. **Replacement difficulty?** Low — implement `SessionStore` once; callers and
   the `AppState` type (`SessionStore`) are unchanged.
4. **Future replacement?** An AIOS store *only if* SQLite blocks a real need
   (e.g. at-rest encryption, sync); otherwise SQLite stays behind the seam
   indefinitely (Constitution: don't replace for vanity).

## Consequences

- The daemon depends on `SessionStore`, not on SQLite.
- Swapping the engine is additive and local to one module.
- Because the interface is domain-shaped, an encrypted or synced store can
  implement it without leaking storage concerns upward.

## Rejected alternatives

- **Model the interface on SQL / cursors.** Rejected — leaks the engine across
  the seam (Constitution §II.5).
- **Add a `store_backend` config knob now.** Rejected — speculative; there is one
  backend. The *selection point* (`open_store`) is centralized; a knob arrives
  with the second backend (Constitution §III.8, no premature abstraction).
