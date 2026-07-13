# ADR 0013 — The SessionManager seam (login/session)

- **Status:** accepted
- **Date:** 2026-07-13
- **Implements:** Constitution §II (replaceability); matrix row #16. Same
  honest-scope precedent as ADR-0011/0012.

## Context

Login/session bring-up is the last major *host-integration* boundary. Today AIOS
registers a Wayland session (`aios.desktop`) that a display manager (GDM on
Fedora Asahi) can launch. For a more AIOS-owned, minimal login, **greetd** is the
natural target — but *which* login manager launches the session should be behind
an interface, not assumed.

## Decision

Add an AIOS-owned **`SessionManager`** interface (`aiosd/session.py`):
`session_command()` (what launches the AIOS session) and `greeter_config()` (the
login-manager configuration). Ship **`GreetdSessionManager`** — the only class
that knows greetd — which generates a greetd config launching `aios-session`
(with optional single-user autologin). `aios session` prints it for the user to
install at `/etc/greetd/config.toml`.

**Honest testability.** greetd runs on the Linux target, not the macOS dev host,
so the **config generation** is unit-tested here; wiring greetd into a booted
system is validated on hardware (docs/asahi-bringup.md). The generator is pure —
no root, no system writes from the tool (it prints; the user installs with sudo).

### The Four Questions

1. **Why greetd?** Minimal, scriptable, AIOS-owned login — a better identity fit
   than depending on GDM, while the `.desktop`/GDM path still works.
2. **Which abstraction isolates it?** `SessionManager` — callers see
   `session_command`/`greeter_config`, never greetd specifics.
3. **Replacement difficulty?** Medium — implement `SessionManager` for an AIOS
   greeter; the CLI/interface are unchanged.
4. **Future replacement?** An AIOS-native greeter/login manager behind the same
   seam.

## Consequences

- With this seam formalized, **every host-specific integration point is now
  behind an AIOS interface**: kernel/host facts (HAL), services (ServiceManager),
  storage (SessionStore), transport (Transport), inference (Backend/Embedder),
  updates (UpdateManager), packages (PackageManager), and login (SessionManager).
- Owning the login layer is additive: a native greeter is a new `SessionManager`.

## Rejected alternatives

- **Only register a `.desktop` and rely on GDM forever.** Rejected — that leaves
  the login layer un-owned; greetd + the seam make it AIOS's.
- **Have the tool write `/etc/greetd/config.toml` directly.** Rejected — root
  system writes belong to the user's deliberate `sudo` step; the tool prints,
  matching `install.sh`'s conservative posture.
