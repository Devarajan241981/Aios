# ADR 0005 — The ServiceManager seam (isolating systemd)

- **Status:** accepted
- **Date:** 2026-07-12
- **Implements:** Constitution §I (layering), §II (replaceability); matrix rows
  #11 (scheduling) and #12 (init/service manager).

## Context

`Scheduler` (a system service) generated systemd unit text, wrote it into
`~/.config/systemd/user`, and shelled out to `systemctl` directly. That is a
Constitution violation: systemd knowledge leaked into a service that must remain
independent of the host init system. It also made "replace systemd with our own
`aiosinit`" a rewrite rather than a swap.

This is the first **Stage 2** seam to formalize — the highest-leverage step
toward owning the userland, because init/service supervision underpins
everything that runs.

## Decision

Introduce an AIOS-owned **`ServiceManager`** interface
(`aiosd/platform/services.py`) covering the two things any init system — systemd
today, `aiosinit` tomorrow — must provide:

- **service lifecycle**: `start` / `stop` / `restart` / `enable` / `disable` /
  `is_active` / `reload`;
- **scheduled jobs**: `schedule(job)` / `unschedule(name)`, where `job` is an
  **AIOS-neutral `ScheduledJob`** (name, friendly `when`, command, description).

`SystemdServiceManager` is the **only** class permitted to know systemd (unit
text, the unit directory, `systemctl`, `OnCalendar`). `NullServiceManager` is a
no-op for hosts without a supported init. `current_service_manager()` selects the
backend.

`Scheduler` is refactored to own only **AIOS-neutral policy** — name validation,
the `aios ask` wrapper, and the automation index — and to **delegate** all OS
registration to an injected `ServiceManager`. It no longer imports or emits
anything systemd-shaped.

### The Four Questions (Constitution §II.4)

1. **Why systemd?** It is the init/service manager of the target base (Fedora
   Asahi); reusing it now is correct (don't reimplement init early).
2. **Which abstraction isolates it?** `ServiceManager` — nothing systemd-shaped
   crosses it; jobs are described in AIOS terms.
3. **Replacement difficulty?** Medium — write one `ServiceManager` implementation
   (`aiosinit`); callers are untouched.
4. **Future replacement?** `aiosinit`, an AIOS service supervisor, behind the same
   interface.

## Consequences

- No AIOS **service** calls `systemctl` or writes units directly anymore.
- Swapping init is additive (a new `ServiceManager`), matching the north star.
- The interface deliberately also models service lifecycle (not just scheduling),
  so migrating daemon supervision (`aiosd.service`) off direct `systemctl` calls
  later is already possible through the same seam.
- Install/bring-up **shell scripts** still use `systemctl` directly. That is
  accepted: they are host bootstrapping, not running AIOS services, and are the
  correct place for host-specific setup. They will target the AIOS installer as
  it matures.

## Rejected alternatives

- **Keep systemd calls in `Scheduler`, "abstract later."** Rejected — the exact
  lock-in the Constitution forbids.
- **Model the interface on systemd units directly.** Rejected — that leaks
  systemd idioms across the seam (Constitution §II.5); a future `aiosinit` would
  be forced to emulate systemd instead of implementing a clean contract.
