# ADR 0010 — The Notification center

- **Status:** accepted
- **Date:** 2026-07-13
- **Implements:** Constitution §I/§II; matrix row #18. A **net-new AIOS service**
  (no legacy dependency to unwind — pure ownership).

## Context

AIOS could *do* things (agent actions, scheduled automations) but had no way to
*tell the user* about them. Notifications are a core OS service. Building it now
is straightforward ownership with a clear identity payoff, and it composes with
existing subsystems (the agent, automations, the audit log).

## Decision

Add an AIOS-owned **`NotificationCenter`** service: notifications are created by
AIOS components, **persisted** locally (JSON, consistent with the vector/
automations indexes), and **delivered through a `NotificationChannel` seam**:

- **in-app** — stored, exposed at `/v1/notifications`, polled by the web UI
  (bell + unread badge) and the `aios notifications` CLI. Always available, ours.
- **desktop** — `DesktopChannel` shells out to freedesktop `notify-send` when
  present; a **no-op** where it isn't (macOS dev, headless). Host-specific
  delivery isolated behind the channel interface.

Producers (so it is real, not dead code):
- the **agent** emits an awareness notification when it performs a *mutating*
  action (composes with the capability/audit model);
- **`aios notify`** for automations/scripts/apps;
- `POST /v1/notifications` for any app.

Endpoints added **additively** to the frozen v1 contract (ADR-0007): new
endpoints only, no existing field touched.

### The Four Questions

1. **Why build it (vs. reuse libnotify)?** The *center* (create/store/list/read)
   is app-facing product, not a host facility — it should be ours. Only the
   desktop *delivery* reuses `notify-send`, behind the channel seam.
2. **Which abstraction isolates the host part?** `NotificationChannel` —
   `DesktopChannel` is the only place that knows `notify-send`.
3. **Replacement difficulty?** Low — add a `NotificationChannel` (e.g. a native
   AIOS toast on our own compositor) without touching producers or the center.
4. **Future replacement?** An AIOS notification daemon + native channels; the
   center and its API stay put.

## Consequences

- Agent actions, automations, and apps can reach the user (in-app + desktop).
- The channel seam means new delivery surfaces are additive.
- Persistence is local and low-volume; capped (`max_keep`) to bound growth.

## Rejected alternatives

- **Depend directly on libnotify/D-Bus in components.** Rejected — leaks a host
  facility across the app boundary (Constitution §I.3); isolated in a channel.
- **Fire-and-forget (no persistence/API).** Rejected — the web UI/CLI need to
  list and mark-read; ephemeral-only would not be a real notification center.
- **Emit a notification for every tool call.** Rejected as noisy — only
  *mutating* actions notify (awareness where it matters).
