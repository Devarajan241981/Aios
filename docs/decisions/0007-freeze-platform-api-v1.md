# ADR 0007 — Freeze the Platform API as v1

- **Status:** accepted
- **Date:** 2026-07-12
- **Implements:** Constitution §I.3 (apps target the Platform API, not the host);
  Stage-1 exit criterion (matrix row #1).

## Context

The Platform API — the `aiosd` service API — is the boundary every application
targets and the thing that makes AIOS independent of the kernel from the app's
point of view. Its biggest long-term risk is **uncontrolled churn**: if the
app-facing contract keeps shifting, every app and the SDK break, and the
"independence" promise is hollow. As Chief Architect I flagged this as the single
most important guardrail (see [01-layered-architecture](../architecture/01-layered-architecture.md),
"freeze the Platform API early").

## Decision

1. **Freeze the application data plane as v1**, served under `/v1/…`. The path
   prefix is the contract version; `api_version` is also advertised in `/health`
   and `/version`.
2. **Publish the contract**:
   [docs/architecture/04-platform-api-v1.md](../architecture/04-platform-api-v1.md)
   documents every endpoint, request/response shape, error model, and auth.
3. **Stability policy — additive only within v1.** Never remove/rename a field,
   change a type, repurpose a value, or tighten validation in a breaking way. A
   breaking change introduces `/v2` alongside `/v1`, with a published deprecation
   window for `/v1`.
4. **Separate planes:** the versioned **application data plane** (`/v1`) vs. the
   stable **operations plane** (`/health`, `/version`, `/config`) vs. the **asset
   plane** (`/`). Only `/v1` carries the frozen app contract; apps must not depend
   on operations-plane shapes.
5. **Enforce with tests, not intentions.** `test_api_contract.py` pins every v1
   shape; drift fails CI. Loosening a contract test to pass a breaking change is
   forbidden — that is what `/v2` is for.

## Consequences

- Apps, the CLI, the web UI, and the future SDK have a dependable target.
- The contract is decoupled from HTTP semantically: when the `Transport` seam
  (matrix #23) moves it onto AIOS message-ports, the documented data contract is
  unchanged.
- We accept a real constraint: new capabilities must fit additively or wait for a
  major-version bump. This is the discipline that keeps a 10-year platform sane.

## Rejected alternatives

- **Leave the API implicit / unversioned.** Rejected — guarantees churn and app
  breakage; the exact 10-year risk this project must avoid.
- **Version every endpoint independently.** Rejected — needless complexity; a
  single contract version with additive evolution is simpler and sufficient.
- **Fold `/health`/`/config` into `/v1`.** Rejected — liveness/introspection are
  operational concerns; binding them into the app contract would freeze
  operational details apps shouldn't depend on.
