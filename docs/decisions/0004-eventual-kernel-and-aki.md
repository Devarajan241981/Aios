# ADR 0004 — The eventual kernel and the AIOS Kernel Interface (AKI)

- **Status:** accepted
- **Date:** 2026-07-12

## Context

Long-term independence implies the kernel itself must eventually be replaceable —
Linux should not be a permanent, load-bearing assumption baked into every layer.
But writing a production kernel now is unrealistic and, done prematurely, would
starve the project's real differentiators (the AI runtime, the app platform, the
desktop) and add unbounded risk.

We need the *option* of our own kernel to stay open forever, at near-zero ongoing
cost, without building it now.

## Decision

1. **Define the AIOS Kernel Interface (AKI) now**
   ([docs/architecture/03](../architecture/03-kernel-design.md)): a minimal,
   capability-oriented, transport-neutral boundary between AIOS system services
   and whatever kernel is underneath. **Linux is the first AKI provider.**
2. **Design the kernel on paper now, implement none of it.** Scheduler, memory,
   IPC, filesystem interface, driver framework, security/capability model, and
   graphics architecture are specified as targets that constrain upper-layer
   choices — not as a build schedule.
3. **Adopt a capability microkernel target.** This aligns the kernel security
   model with the app-level capability model already shipped (tool approval,
   per-session grants, audit) — one coherent security philosophy across all
   layers.
4. **Constrain upper layers to stay kernel-agnostic:** prefer message passing,
   capability handles, and userspace services; reach host/kernel specifics only
   through the HAL/AKI. The `Platform` HAL is the first enforcement of this.

## Consequences

- Removing Linux later is an **additive AKI provider**, not a rewrite — the
  non-dead-end the Constitution requires.
- Today's designs pay a small "kernel-agnostic tax" (no casual assumption of a
  monolithic Linux), which is exactly the discipline we want.
- We explicitly accept that a native kernel may **never** be built; the AKI's
  value is preserved optionality and clean layering regardless.

## Non-goals

- No kernel, filesystem, libc, or GPU-driver implementation in the foreseeable
  future. This ADR keeps the door open; it is not a commitment to walk through it
  soon.

## Rejected alternatives

- **Start writing a kernel now.** Rejected: unrealistic, ruinous to focus and
  risk; violates Constitution Articles 8 and 14.
- **Never plan for kernel independence; treat Linux as permanent.** Rejected:
  that is the lock-in dead-end (Article 7); it forecloses the project's stated
  long-term identity.
