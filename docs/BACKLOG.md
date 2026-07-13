# AIOS Backlog — deferred & future work

Durable list of what's intentionally not done yet, with *why*. Ordered roughly by
when it becomes doable. Each item, when started, gets a matrix row + (usually) an
ADR, per the [Engineering Constitution](architecture/00-engineering-constitution.md).

Status of the seam programme so far: HAL, ServiceManager, SessionStore,
Transport, Inference, UpdateManager, PackageManager formalized; Platform API v1
frozen; Notification center + automations→notifications shipped.

## A. Needs the M4 / Asahi Linux (hardware-gated)

Only runnable on the target hardware; scripts/specs exist, execution is yours.

- [ ] **Boot Asahi Linux on the M4 and run `scripts/asahi-bringup.sh`** — the real
      next milestone. `aios doctor` verifies the result.
- [ ] Validate the Sway session end-to-end: panel, overlay (`Super+Space`),
      launcher (`Super+D`), kiosk web-UI shell, `aiosd` systemd user service.
- [ ] Exercise the **desktop `notify-send` channel** and **automation timers**
      under real systemd.
- [ ] GPU acceleration status on Asahi (expect software/basic rendering initially).

## B. Large Stage-2 builds (buildable incrementally; some execution Linux-only)

- [ ] **Compositor / window-manager seam** (matrix #15) — own the *shell
      protocol/policy*; keep wlroots as a library provider. Do **not** write a
      compositor from scratch (ADR-0003 challenge).
- [x] **AIOS SDK** (matrix #22) — zero-dependency Python client over Platform API
      v1 (`sdk/aios_sdk`, ADR-0014). Remaining: more language bindings.
- [ ] **UI toolkit** (matrix #17) — an AIOS UI toolkit beyond the web UI.
- [ ] **Native file manager** (matrix #21) — an app over the Platform API.
- [ ] **Settings service** (matrix #7) — an AIOS settings surface over config.
- [ ] **Session/login greeter** (matrix #16) — `greetd`-based AIOS greeter behind
      a `SessionManager` seam.
- [ ] **Workspace switcher UI** in the panel.
- [ ] **`aiosinit`** — an AIOS service supervisor implementing the existing
      `ServiceManager` interface (replace systemd behind the seam).
- [ ] **Atomic/image UpdateManager** — an ostree-style `UpdateManager` impl for
      when AIOS ships as an image (interface already exists; ADR-0011).

## C. Stage 3 (define-first, build-maybe-never)

- [ ] **AIOS kernel** — a capability microkernel (designed in
      [03-kernel-design.md](architecture/03-kernel-design.md), not built). Value
      today is the AKI boundary keeping Linux swappable.
- [ ] **AIOS IPC (message ports)** — a `Transport` impl replacing HTTP; the
      frozen v1 contract rides it unchanged (seam ready, ADR-0008).
- [ ] Filesystem / libc / GPU driver — deliberately **not** planned; use Linux's
      (ADR-0004 non-goals).

## D. Polish & maintainability (doable here anytime)

- [ ] `CONTRIBUTING.md` + an architecture onboarding guide (make the 10-year
      project maintainable by others).
- [ ] More notification channels (e.g. native AIOS toast on our compositor).
- [ ] Streaming for tool-using chat responses.
- [ ] Encrypt the semantic index / audit / notifications at rest.
- [ ] Incremental re-index (mtime tracking) for the semantic memory.
- [ ] Richer `write_file` previews already done; add move/rename previews with
      conflict detection.
- [ ] Per-tool (not just per-session) permission scopes.
