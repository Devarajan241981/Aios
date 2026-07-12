# ADR 0008 — The Transport seam (decoupling the API from HTTP/TCP)

- **Status:** accepted
- **Date:** 2026-07-12
- **Implements:** Constitution §II (replaceability); matrix row #23. Extends the
  Platform API freeze ([ADR-0007](0007-freeze-platform-api-v1.md)): contract
  frozen; transport now independent.

## Context

Applications reach `aiosd` over loopback **HTTP/TCP**. That medium was baked into
the server. Two problems: (1) a TCP port — even on loopback — is more exposed
than necessary for a single-user local service; (2) welding the app contract to
HTTP/TCP would block the Stage-3 move to AIOS message-ports. The v1 contract is
*what* apps say; it should not be permanently tied to *how* the bytes travel.

## Decision

Introduce a **`Transport`** interface (`aiosd/transport.py`) that owns how a
request handler is served, with **two shipping implementations** (which is what
makes the seam real, not speculative — Constitution §III.8):

- **`TcpHttpTransport`** — HTTP over loopback TCP. Default; required by the
  browser web UI.
- **`UnixHttpTransport`** — the *same* HTTP handler over a Unix-domain socket:
  **no network port at all**, access controlled by filesystem permissions
  (mode `0600`, owner-only), socket cleaned up on shutdown.

Both reuse the identical request handler, so endpoint logic is transport-agnostic
by construction. `make_transport(config)` selects one (`AIOS_TRANSPORT`,
`AIOS_SOCKET_PATH`). The frozen v1 contract is served **unchanged** over either —
verified by the transport tests (health + chat over the Unix socket).

### The Four Questions

1. **Why HTTP/TCP?** Ubiquitous, the browser UI needs it, trivial clients.
2. **Which abstraction isolates it?** `Transport` — request handling never
   touches the socket family or framing decision.
3. **Replacement difficulty?** Medium — add a `Transport` implementation; the
   handler and the v1 contract are untouched.
4. **Future replacement?** AIOS message-ports (Stage 3), behind the same seam;
   the Unix-socket transport is the intermediate proof and a security win today.

## Consequences

- AIOS can run with **zero TCP exposure** (`AIOS_TRANSPORT=unix`) for
  CLI/SDK/programmatic use; the browser UI uses TCP.
- The contract is now decoupled from HTTP *semantically*: moving to message-ports
  is an additive `Transport`, not a contract change.
- Honest limitation: browsers cannot use Unix sockets, so TCP remains the default
  and the web-UI transport. Running both simultaneously is a possible future
  addition; not needed yet (no premature build).

## Rejected alternatives

- **Keep HTTP/TCP hard-wired, "abstract later."** Rejected — lock-in the
  Constitution forbids, and it would tie the just-frozen contract to a medium.
- **Introduce the interface with only the TCP impl.** Rejected — that is the
  speculative-abstraction failure mode (§III.8). A second real implementation
  (Unix socket, with genuine value) proves the seam.
