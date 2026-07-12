# ADR 0009 — The Inference seam (model runtime)

- **Status:** accepted
- **Date:** 2026-07-12
- **Implements:** Constitution §II (replaceability); matrix rows #2/#3/#4.

## Context

The model runtime — text generation and embeddings — is the core of "MY OS".
Reviewing it for the Stage-2 pass, I found the seam was **already well-factored**
by earlier work: `Backend` (generation) and `Embedder` (embeddings) are clean
interfaces with `make_backend` / `make_embedder` selection points, and the mock /
hashing implementations already exercise the abstraction.

The Constitution is explicit that we do **not** churn working code or add
abstraction for its own sake (§III.8, Article 14). So this ADR **formalizes** the
existing seam and fixes the one real gap, rather than rewriting anything.

## Decision

1. **Recognize the Inference seam as two interfaces, not one bundle.**
   - `Backend` — generation: `chat`, `stream_chat`, `chat_with_tools`, `health`.
   - `Embedder` — embeddings: `embed`.
   They are **deliberately kept separate and mixable** (e.g. `AIOS_BACKEND=ollama`
   with `AIOS_EMBEDDINGS=hashing`). Bundling them into a single "provider" would
   *reduce* real flexibility and is rejected as over-abstraction.

2. **Selection points stay** `make_backend(config)` and `make_embedder(config)`
   (matching the project's `make_*` factory style). Not renamed — cosmetic
   consistency is not worth breaking imports across the daemon and tests.

3. **Fill the observability gap:** embeddings readiness was invisible — a
   mis-pulled Ollama embedding model only failed at index/search time.
   `aios doctor` now reports an **embeddings** check, computed from data it
   already fetches (`/config` embeddings + embed_model, `/health` backend model
   list) — **no new endpoint, no new I/O, no change to the frozen `/health`
   contract.**

### The Four Questions

1. **Why Ollama / llama.cpp?** Mature local inference runtimes; we don't own a
   trained-model runtime and shouldn't build one now.
2. **Which abstraction isolates it?** `Backend` and `Embedder` — the daemon,
   assistant, indexer, and retriever depend only on these.
3. **Replacement difficulty?** Low — implement `Backend` / `Embedder` for a new
   runtime; callers and the API are untouched. (The `HashingEmbedder` proves a
   fully-owned embedder already ships.)
4. **Future replacement?** An **AIOS inference engine** (likely `llama.cpp` as a
   library first, then increasingly our own), behind the same two interfaces.

## Consequences

- The inference boundary is documented and its readiness is diagnosable.
- Swapping the model runtime is additive and local to the two factories.
- We keep the valuable ability to mix a heavy generation backend with a
  zero-download offline embedder.

## Rejected alternatives

- **Bundle generation + embeddings into one `InferenceProvider`.** Rejected —
  removes mixing, adds indirection, no benefit today (§III.8).
- **Rename the factories for cosmetic consistency.** Rejected — pure churn across
  callers/tests (Article 14: maintainability over vanity).
- **Add `Embedder.health()` wired into `/health`.** Rejected for now — it would
  add a per-poll network call and either dead code or a frozen-contract change;
  `doctor` covers the readiness need with zero new I/O.
