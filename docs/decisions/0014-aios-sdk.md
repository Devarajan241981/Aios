# ADR 0014 — The AIOS SDK

- **Status:** accepted
- **Date:** 2026-07-13
- **Implements:** matrix row #22; the developer-facing half of the Platform API
  boundary (Constitution §I.3). Depends on [ADR-0007](0007-freeze-platform-api-v1.md)
  (frozen v1 contract).

## Context

Freezing the Platform API v1 gave apps a stable contract — but they still had to
hand-roll HTTP against it (as `bin/aios` does). For AIOS to be a *platform* others
build on, it needs a first-class **SDK**: a typed client so apps target AIOS, not
HTTP, and remain oblivious to the host OS/kernel (the point of the boundary).

## Decision

Ship **`aios_sdk`** — a standalone, **zero-dependency** Python client
(`sdk/aios_sdk`), versioned to Platform API v1:

- `AIOSClient` maps one method to each `/v1` endpoint (ask/stream/search/index,
  sessions + grants, tools, notifications, audit), plus the operations plane
  (health/version). Typed returns (`ChatResult`, `Session`, `Notification`,
  `SearchResult`); tolerant of additive API growth (unknown fields ignored).
- Errors are typed: `APIError(status, message)`, `AIOSConnectionError`.
- It is a **separate package** from the daemon (`aiosd`): the SDK is a pure
  client and never imports the server. Its own `pyproject.toml`.

Tests are **integration** tests: they stand up a real `aiosd` (mock backend) and
drive the SDK against it — proving the client works against the actual daemon and
the frozen contract, not a mock of the API. Wired into `make test` and CI as a
second suite.

## Consequences

- Third-party apps, scripts, and future first-party apps have a clean target.
- The SDK is the reference consumer that will catch accidental v1 breakage
  alongside the contract tests.
- Because it only speaks the v1 data contract, it is transport-agnostic — it will
  work unchanged when the API rides the Unix-socket or message-port `Transport`.

## Rejected alternatives

- **Make apps use raw HTTP.** Rejected — no ergonomics, and every app re-derives
  the contract; a platform needs an SDK.
- **Bundle the SDK inside the `aiosd` daemon package.** Rejected — client and
  server are distinct deliverables; the SDK must not depend on the server.
- **Add non-stdlib HTTP deps (requests/httpx).** Rejected — the whole project is
  zero-dependency; `urllib` is sufficient.

## Future

- More language bindings (matrix #22) over the same v1 contract.
- Optionally refactor `bin/aios` onto the SDK (backlog) to dogfood it.
