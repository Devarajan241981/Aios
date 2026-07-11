# ADR 0002 — Tool use and its safety model

- **Status:** accepted
- **Date:** 2026-07-11

## Context

For the assistant to be genuinely useful in an OS, it must be able to *act* —
read files, inspect the system, search the user's notes — not just talk. Letting
a language model drive real actions on someone's machine is also the single
biggest risk surface in the whole project. We need capability **and** a safety
model that holds even when the model is wrong or adversarially prompted.

## Decision

1. **Tools are explicit, typed capabilities.** Each `Tool` has a name, a
   description, a JSON-Schema for its arguments, and a Python function. The model
   only ever sees the schemas; it cannot invent new capabilities.

2. **Least privilege on the filesystem.** `read_file` / `list_dir` resolve paths
   with `os.path.realpath` and reject anything outside the user's home plus
   explicitly configured `AIOS_ALLOWED_ROOTS`. Realpath resolution defeats
   symlink escapes.

3. **Safe-by-default, gated-when-not.** Every tool declares `safe` (read-only /
   side-effect-free). Safe tools run automatically. A non-safe (mutating) tool is
   **never executed without approval**. We ship two mutating tools — `write_file`
   and `run_command` (allowlisted, no shell, 10s timeout) — behind the
   preview-before-run gate below.

3a. **Preview-before-run, with content-addressed approval.** When the model
   requests an unapproved mutating tool, the agent **halts before executing
   anything in that turn** and returns the pending action(s), each with a
   human-readable `preview` (computed by a side-effect-free preview function) and
   a `signature` — a SHA-256 over the tool name + arguments. The caller shows the
   preview, and to proceed re-runs the request with the approved signatures. A
   mutating call executes **only if its signature was approved**; if the model
   produces a *different* call, it halts again with a fresh preview. This keeps
   the flow stateless over HTTP while guaranteeing the user runs exactly what
   they previewed — "the model decided to" is never sufficient.

4. **Tools cannot crash the daemon.** Every tool invocation is wrapped; failures
   become structured `{"ok": false, "error": ...}` results fed back to the model,
   never uncaught exceptions.

5. **Backend-agnostic agent loop.** The agent speaks one normalized message
   format; each backend translates to its wire protocol. This keeps tool logic
   testable with a scripted backend and avoids coupling to one model vendor.

6. **Tool use is opt-in per request** (`use_tools: true`) and can be disabled
   daemon-wide (`AIOS_TOOLS=off`).

## Consequences

- The assistant can answer questions like "what's in my Downloads folder?" or
  "search my notes for the budget" by calling tools, entirely locally.
- The blast radius of a hallucinated or injected tool call is bounded by the
  sandbox and the approval gate.
- Adding a new safe tool is a few lines; adding a mutating tool forces us to also
  design its confirmation UX before it can ever run.

## Status of the plan

Done: the preview-before-run gate, content-addressed approval, and the first two
mutating tools (`write_file`, `run_command`) with an interactive CLI approval
loop (`aios ask --tools`) and a non-interactive `--approve`.

## Future work

- Richer previews (e.g. a real diff for `write_file` overwrites).
- Per-tool and per-session permission scopes (grant `write_file` for a session).
- A persistent audit log of every tool invocation and approval.
- More mutating tools (move/delete with trash semantics, package operations)
  behind the same gate.
