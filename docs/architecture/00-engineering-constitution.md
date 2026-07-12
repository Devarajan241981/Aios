# The AIOS Engineering Constitution

> The rules that govern this codebase for the next decade. They exist to keep
> AIOS **independent, modular, and replaceable** as it evolves from a
> Linux-based foundation toward an increasingly self-owned operating system —
> while remaining usable at every stage.
>
> This document is normative. Changing an article requires an ADR
> (`docs/decisions/`). Code review rejects violations.

## Prime directive

**AIOS owns its interfaces. Third-party components are implementations behind
those interfaces, never the interface itself.** Independence is achieved by
controlling every *seam*, not by reimplementing every component today.

## The articles

### I. Layering
1. Every layer talks only to the layer directly below it, **through an
   AIOS-owned interface**. No layer reaches around another.
2. **No component above the HAL knows which kernel or host OS it runs on.**
3. Application-facing code MUST use the **AIOS Platform API** (the `aiosd`
   service API). It MUST NOT use Linux, systemd, or POSIX APIs directly.

### II. Replaceability
4. Every external dependency MUST be isolated behind an AIOS interface and have
   a row in the [Dependency Replacement Matrix](02-dependency-replacement-matrix.md)
   answering: *why we use it, which abstraction isolates it, how hard it is to
   replace, and what replaces it.*
5. No dependency may leak its types, error shapes, or idioms across its
   interface. If removing a library would force edits above its seam, the seam
   is wrong.
6. Adopting a new dependency requires an ADR. Removing one should touch only its
   adapter.

### III. Anti-dead-end (the two failure modes)
7. **Never lock in.** No design may make a future replacement impossible. The
   test: *"Could we swap this implementation in one module?"* must stay "yes."
8. **Never over-abstract.** Interfaces are introduced at **proven seams** where a
   real second implementation is foreseeable — not speculatively everywhere.
   Abstraction sludge is as fatal as lock-in. When in doubt, name the seam in a
   doc now; build the indirection when the second implementation is real.

### IV. Modularity & interfaces
9. Every subsystem is a module with a documented public interface and a single
   responsibility. Internals are private.
10. Interfaces are **narrow, explicit, and stable**; implementations are free to
    change. Breaking a public interface requires a version bump and a migration
    note.

### V. Quality (non-negotiable)
11. Every feature ships with automated tests. Every bug fix ships with a
    regression test.
12. Every commit passes CI. Main is always green.
13. Every public interface has documentation. Every major decision has an ADR.
14. Production-quality only: prefer **architecture over speed, maintainability
    over cleverness, extensibility over convenience.** No knowingly-incurred
    technical debt without a tracked, ADR-justified reason.

### VI. Security
15. **Capabilities, not ambient authority.** A component gets exactly the access
    it is handed, nothing more. This principle spans every layer — the app tool
    model today, the kernel capability model tomorrow (they are the same idea).
16. No secret in code or logs. Loopback-only by default. Nothing leaves the
    device without explicit, per-use consent.

## The Four Questions (mandatory for every adopted dependency)

Answered in the matrix, and in the adopting ADR:

1. **Why are we using it?** (What need, why not build now.)
2. **Which abstraction isolates it?** (The exact AIOS interface / module.)
3. **How difficult will it be to replace?** (Trivial · Low · Medium · High · Extreme.)
4. **What is our future replacement?** (Named target, and the stage.)

## How we decide *whether to replace* something

Replace an implementation only when at least one is true:
- it **blocks** a capability we need, or
- it **compromises** independence/security/privacy at the interface, or
- **owning it is itself the differentiator** (the AI runtime, the app API, the
  desktop identity, the capability/security model).

Otherwise: keep the third-party implementation **behind our interface** and move
on. Reimplementing for its own sake violates Article 14 (convenience/vanity is
not extensibility) and Article 8.

## What "MY operating system" means here

Identity is not "we rewrote the file manager." Identity is:
- the **AI runtime and agent** (ours),
- the **application platform API** apps are written against (ours),
- the **capability/permission and safety model** (ours),
- the **desktop experience and shell** (increasingly ours),

all sitting on interfaces we own, over a kernel that is — for now — Linux, and
**replaceable by design.**
