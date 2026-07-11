# ADR 0001 — Scope and build strategy

- **Status:** accepted
- **Date:** 2026-07-11

## Context

The founding research report proposed a "free, solo-developed desktop OS" for
Apple Silicon combining a Linux kernel (with Apple patches), a Wayland desktop,
and deep local-AI integration. Taken literally, that spans kernel work, driver
reverse-engineering, a full desktop environment, and an AI stack — years of work
for a team, let alone one developer.

We need a scope that (a) is achievable solo, (b) produces something runnable
early, and (c) still delivers the report's actual differentiator: a private,
local, AI-native experience.

## Decision

1. **AIOS is a desktop + AI layer on an existing Linux base, not a new OS
   kernel.** Target base: Asahi Linux on the MacBook Air M4. We consume its
   kernel and drivers; we do not fork or patch them.
2. **Build the AI core first, on macOS, before any Linux/hardware work.** It's
   the differentiator and it has no OS dependencies. This is Phase 1 and it is
   already running.
3. **Python + standard library only for Phase 1.** Zero pip dependencies →
   guaranteed to run on the installed Python 3.14, trivial to test in CI. The
   HTTP contract is the stable interface; the implementation language behind it
   can change.
4. **One backend abstraction speaking the OpenAI chat API.** Covers Ollama,
   llama.cpp-server, and LocalAI with a single code path. A mock backend keeps
   the whole system testable and demonstrable offline.
5. **Loopback-only, no telemetry, local-by-default** is a hard product
   invariant, enforced from day one (bind address, no outbound calls).

## Consequences

- We can dogfood the assistant immediately, long before the desktop exists.
- Moving to the M4/Asahi (Phase 3) does not require rewriting the AI core — the
  same `aiosd` runs there as a systemd user service.
- A future Rust rewrite of `aiosd` (better fit for an always-on system daemon)
  is a contained task behind the existing HTTP contract, not a rearchitecture.
- We explicitly defer: kernel/driver work, GPU acceleration guarantees, voice,
  and cloud sync. See [ROADMAP.md](../../ROADMAP.md).

## Rejected alternatives

- **Write/fork a kernel (or use a Rust microkernel like Redox).** Not mature
  enough for a daily-driver desktop and vastly beyond solo scope.
- **Start with the desktop shell.** Higher effort, and useless without the AI
  core it's meant to surface. Shell comes after the core works.
- **Cloud-hosted models for convenience.** Violates the local-first invariant;
  optional remote endpoints remain possible but never the default.
