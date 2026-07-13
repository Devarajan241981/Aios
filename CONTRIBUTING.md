# Contributing to AIOS

AIOS is built to be maintained for 10+ years and to evolve from a Linux-hosted
foundation toward an increasingly independent OS. That longevity depends on a
few firm rules. Please read the
**[Engineering Constitution](docs/architecture/00-engineering-constitution.md)**
first — it is normative, and reviews enforce it.

## The one-paragraph mental model

AIOS owns two boundaries and everything between them. Apps target the **Platform
API v1** (the `aiosd` service API) and never touch the host. Everything
host/kernel-specific is reached only through the **HAL / seams** below the system
services. Linux is a temporary, replaceable layer. See
[docs/architecture/](docs/architecture/).

## Project layout

```
ai-core/aiosd/     the daemon (one module per subsystem; interfaces + impls)
ai-core/tests/     daemon test suite
bin/aios           the CLI client
sdk/aios_sdk/      the developer SDK (client for Platform API v1)
sdk/tests/         SDK + examples integration tests
examples/          small apps built on the SDK
docs/architecture/ the layered architecture, matrix, kernel design, API v1 spec
docs/decisions/    ADRs — one per significant decision
docs/BACKLOG.md    deferred work
packaging/ scripts/  desktop session, install, bring-up
```

## Setup & running

Standard library only — no `pip install` needed to run or test.

```bash
make mock            # start the daemon with the offline mock backend
make test            # run BOTH suites (daemon + SDK); must be green
make lint            # byte-compile sanity check
./bin/aios doctor    # diagnose a running setup
```

For a real local model: `ollama serve` + `ollama pull llama3.2`, then `make run`.

## The Golden Rules (short form of the Constitution)

1. **Own the interface.** A third-party thing (systemd, SQLite, Flatpak, Ollama)
   is an *implementation behind an AIOS interface*, never the interface.
2. **Nothing above the HAL knows the host/kernel.** No Linux/systemd/POSIX use
   above the HAL; apps use only the Platform API.
3. **Interfaces at proven seams — not everywhere.** Avoid speculative
   abstraction as fiercely as lock-in.
4. **Tests for everything. CI green. ADR + matrix row for every dependency.**
5. **Capabilities, not ambient authority** (tool approvals → kernel caps).
6. **Zero third-party dependencies.** stdlib only, by design.

## How to add or replace a dependency (the seam pattern)

Every host/external dependency follows the same shape. Copy an existing seam
(`aiosd/platform/services.py`, `storage.py`, `transport.py`, `packages.py`,
`session.py`, `update.py`) — they are all identical in structure:

1. **Interface** — an ABC in AIOS-neutral terms (no vendor idioms cross it).
2. **Implementation** — the *only* class that knows the third-party thing.
3. **Selection point** — one `make_*` / `open_*` / `current_*` factory.
4. **Callers depend on the interface**, obtained from the factory.
5. **Answer the Four Questions** (why we use it · which abstraction isolates it ·
   replacement difficulty · future replacement) in an **ADR** and a **row in the
   [Dependency Replacement Matrix](docs/architecture/02-dependency-replacement-matrix.md)**.
6. **Tests** — pure logic + graceful degradation. If a dependency can't run on the
   dev host (e.g. flatpak, greetd), test parsing/generation/degradation here and
   say so honestly in the ADR; execution is validated on the Linux target.

## Coding standards

- Small modules, one responsibility, documented public interface.
- Best-effort host code **never raises** across a seam.
- No secrets in code/logs; loopback-only by default; nothing leaves the device
  without explicit consent.
- Match the surrounding style; keep functions readable over clever.

## Commits & PRs

- One logical change per commit; imperative subject; explain *why*.
- `make test` green (both suites). New behavior ships with tests; bug fixes ship
  with a regression test.
- A significant decision ⇒ an **ADR** (`docs/decisions/NNNN-*.md`) and, if it
  adopts/replaces a dependency, a **matrix** update.
- The **Platform API v1 is frozen**: additive changes only; a breaking change
  means `/v2` (see [ADR-0007](docs/decisions/0007-freeze-platform-api-v1.md)).
  `sdk/tests` and `ai-core/tests/test_api_contract.py` guard it.

## Where to look

- **Why it's built this way:** [ADRs](docs/decisions/) (0001–0014).
- **The plan:** [ROADMAP.md](ROADMAP.md) and [docs/BACKLOG.md](docs/BACKLOG.md).
- **The contract:** [Platform API v1](docs/architecture/04-platform-api-v1.md).
