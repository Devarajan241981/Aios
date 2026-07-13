# ADR 0011 — The UpdateManager seam

- **Status:** accepted
- **Date:** 2026-07-13
- **Implements:** Constitution §II (replaceability); matrix row #20.

## Context

AIOS had no first-class answer to "how do I update it?" — just a manual
`git pull`. Updating is a core OS responsibility and its *mechanism* must be
swappable: today AIOS is a **git checkout**; at Stage 3 it will be an **atomic
image**. Building a full ostree/image updater now would be unverifiable on the
development machine and premature (Constitution Articles 8 and 14). So we define
the seam and implement the mechanism that matches the **current deployment
stage** — honestly and testably.

## Decision

Add an AIOS-owned **`UpdateManager`** interface (`aiosd/update.py`) with two
operations: `status()` (read-only) and `apply()`. Ship **`GitUpdateManager`** —
the only implementation that knows git — reflecting today's git-checkout
deployment:

- `status()` fetches the tracked branch and reports current/latest commit, how
  many commits behind, whether an update is available, and whether the tree is
  clean. **No side effects.**
- `apply()` is **safety-gated**: it refuses when the working tree is dirty (never
  clobbers local changes) and only **fast-forwards** (`git pull --ff-only`, never
  a force-merge). On success it reports `from → to`.

`aios update` surfaces it (status by default; `--apply` to fast-forward, then a
notification and a restart hint). It is a **CLI-local ops tool** (like
`aios schedule`), not a daemon endpoint — updating the code the daemon runs, from
that daemon, would be self-modifying and unsafe.

### The Four Questions

1. **Why git-pull?** It is *literally* how the current (repo-based) AIOS is
   deployed; anything else would be fiction at this stage.
2. **Which abstraction isolates it?** `UpdateManager` — callers see `status`/
   `apply`, never git.
3. **Replacement difficulty?** Medium — add an `UpdateManager` for atomic/image
   updates; the CLI and the interface are unchanged.
4. **Future replacement?** An AIOS atomic/image updater (ostree-style) once AIOS
   ships as an image, behind the same seam.

## Consequences

- `aios update` gives a real, safe update path for the current deployment.
- Moving to atomic image updates is an additive `UpdateManager`, not a rewrite.
- Fully testable **here** (against a temporary git repo), unlike a speculative
  image updater — honoring the "test everything" rule.

## Rejected alternatives

- **Build an ostree/atomic updater now.** Rejected — unverifiable on the dev
  machine, premature, and it would starve verifiable work (Articles 8/14).
- **Expose update as a daemon endpoint.** Rejected — self-modifying and unsafe;
  updating is host/deploy ops, kept CLI-local.
- **Force-merge / auto-stash on apply.** Rejected — could destroy local changes;
  refuse-when-dirty + fast-forward-only is the safe contract.
