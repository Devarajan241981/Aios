# AIOS Kernel Design & the AIOS Kernel Interface (AKI)

**Status: design only. No kernel implementation exists or is planned near-term.**

This document exists so the kernel is a *deliberate boundary from day one*. Its
near-term deliverable is the **AKI** — the interface that lets Linux be a
*provider* of kernel services and lets a future AIOS kernel be a drop-in
alternative provider. Writing the kernel is a Stage-3, multi-year, possibly-never
undertaking; keeping it *possible* forever is a Stage-1 discipline.

Why design it now if we won't build it: because every choice above the kernel
(IPC style, security model, graphics path, driver boundaries) either preserves or
destroys the option. We design the target so today's decisions stay compatible.

## The AIOS Kernel Interface (AKI)

The AKI is the single boundary between AIOS system services and *whatever kernel
is underneath*. It is **capability-oriented** and **transport-neutral**.

```
AIOS system services
        │
      [ AKI ]  ── tasks · memory · IPC/ports · objects(files/devices) · time · caps
        │
   ┌────┴─────────────┐
   │ Linux AKI provider│  (today: maps AKI onto Linux syscalls/epoll/io_uring/DRM)
   └───────────────────┘
   ┌───────────────────┐
   │ AIOS kernel provider│  (future: native)
   └───────────────────┘
```

AKI surface (initial, minimal): `spawn/exit`, `port_create/send/recv`,
`mem_map/grant`, `obj_open/read/write` (files & devices as capability handles),
`time/timer`, `cap_derive/revoke`. Everything else (process management, service
supervision, drivers) is built *above* AKI in userland where possible.

## Kernel philosophy: capability microkernel

- **Minimal trusted computing base.** The kernel does tasks, memory, IPC, and
  capabilities. Drivers, filesystems, network stacks, and policy live in
  userspace.
- **Capabilities, not ambient authority.** Access is an unforgeable handle you
  were given. This is *the same model as the AIOS tool-permission system* — the
  security philosophy is coherent from `write_file` approval up to page grants.
- **Message passing over shared global state.** Composition and fault isolation
  beat a monolith for a system meant to evolve for a decade.

## Subsystem designs (targets)

### Scheduler
- Multi-class: a **real-time band** (audio, input, compositor frames) above a
  **fair-share band** (CFS-like weighted fair queuing) above **background/batch**.
- Tickless where possible; energy-aware on Apple Silicon (P/E cores).
- Interface: threads carry a scheduling class capability; UI latency is a
  first-class SLO, not an afterthought.

### Memory management
- Paged virtual memory; per-address-space capability tables.
- **Zero-copy IPC** via memory grants (map a region into a peer with a derived,
  revocable capability) — critical for the graphics and inference paths.
- Explicit, accountable memory (every page attributable to a task/cgroup-equiv).

### IPC
- Two primitives: **synchronous call** (RPC-like, for request/response) and
  **asynchronous ports** (message queues, for events/streams).
- **Capabilities are passed in messages** — how a service hands a client exactly
  one file/device handle and no more.
- Transport-neutral: same API whether backed by Linux (io_uring/unix sockets) or
  our kernel.

### Filesystem interface
- **Object/handle based, not path-syscall-locked.** Open yields a capability;
  operations are on the handle. Namespaces are composable per-process (a service
  can be given a *view*, not the whole tree).
- VFS is a userspace service above AKI `obj_*`. btrfs/ext4 remain valid backends
  indefinitely; an AIOS FS is optional and Extreme-difficulty (see matrix #26).

### Driver framework
- **Userspace drivers**, each holding only the device capabilities it needs;
  crash-isolated and **restartable** without taking down the system.
- A driver is just a service that owns a device object handle — no special kernel
  privilege beyond the capability it was granted.

### Security & capability system
- Unforgeable, delegatable, **revocable** capabilities as the sole authority.
- No global root ambient authority; "root-equivalent" is just holding powerful
  capabilities, which are auditable and revocable.
- Directly continues the app-level model already shipped: preview-before-run,
  per-session grants, and the audit log are the userland face of the same idea.

### Graphics architecture
- Compositor is a **userspace service** holding GPU + display capabilities.
- Zero-copy buffer sharing (memory grants) between apps → compositor → scanout.
- On Linux today this maps to DRM/KMS + Mesa (Asahi); on our kernel, to native
  GPU drivers behind the same compositor-facing interface.

## What this buys us today

- Concrete constraints on upper layers: **prefer message passing, capability
  handles, and userspace services** so nothing accidentally assumes a monolithic
  Linux. The `Platform` HAL and the `aiosd` capability model already reflect this.
- A north star that makes "remove Linux later" an **additive AKI provider**, not
  a rewrite — exactly the non-dead-end the Constitution demands.

## Non-goals (honesty)

- We are **not** writing a kernel, filesystem, libc, or GPU driver in the
  foreseeable future. Attempting it now would violate the Constitution
  (speed/vanity over architecture, unbounded risk) and starve the actual
  differentiators. This doc keeps the door open; it is not a schedule.
