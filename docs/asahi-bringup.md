# Bringing up AIOS on Apple Silicon (Asahi Linux)

This is the Phase 3 path: turn a MacBook (M-series) into an AIOS machine where the
AI core runs as a system service and the web UI is the desktop shell.

> **Status.** The scripts and session config here are written and syntax-checked,
> but full validation requires the actual hardware — they have not yet been run on
> a booted Asahi system. Treat this as the bring-up plan plus ready-to-run tooling.

## 0. Prerequisites

- A MacBook with Apple Silicon (target: **MacBook Air M4**).
- **Fedora Asahi Remix** installed via the official Asahi Linux installer
  (<https://asahilinux.org>). Apple Silicon Macs boot custom kernels without a
  jailbreak; the Asahi installer handles partitioning and the `m1n1` bootloader.
- A working network connection for the first-time package install.

> GPU acceleration on Asahi is still maturing. Expect software/basic rendering on
> the M4 for now — the AIOS shell (a browser + a local HTTP service) does not need
> a GPU. See [ROADMAP.md](../ROADMAP.md).

## 1. One-command bring-up

From a checkout of this repo on the Asahi machine:

```bash
git clone https://github.com/Devarajan241981/Aios.git
cd Aios
./scripts/asahi-bringup.sh          # add --dry-run first to preview every step
```

This installs the session packages (Sway, a terminal, a browser), optionally
points you at Ollama for local models, and runs the user-level AIOS installer.

## 2. What the installer does (`scripts/install.sh`)

- Symlinks the `aios` CLI into `~/.local/bin`.
- Installs `aios-shell` and `aios-session` into `~/.local/bin`.
- Installs the Sway session config to `~/.config/aios/sway/config`.
- Generates and enables the `aiosd` **systemd user service** (hardened unit from
  `packaging/systemd/aiosd.service`).
- Prints the single root step: registering the login session
  (`/usr/share/wayland-sessions/aios.desktop`).

Everything is user-level and idempotent; re-running is safe.

## 3. Log in to AIOS

Register the session (once, as root):

```bash
sudo install -m 0644 packaging/desktop/aios.desktop /usr/share/wayland-sessions/aios.desktop
```

Then log out and pick **AIOS** at the display-manager session menu — or start it
directly from a TTY:

```bash
aios-session
```

### Optional: an AIOS-owned login with greetd

For a minimal, AIOS-native login (instead of GDM), install **greetd** + a greeter
(e.g. `tuigreet`) and generate the config:

```bash
sudo dnf install -y greetd tuigreet          # or your distro's packages
aios session --autologin "$USER" | sudo tee /etc/greetd/config.toml
sudo systemctl enable --now greetd
```

`aios session` prints a greetd config that launches `aios-session` (drop
`--autologin` to show a login prompt instead of auto-logging-in).

Sway starts, ensures `aiosd` is running, and launches the web UI fullscreen as
the shell. `Super+Return` opens a terminal; `Super+Shift+e` exits the session.

## 4. Local models

For real (non-mock) answers, install Ollama and pull a small model:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2
systemctl --user restart aiosd    # picks up the ollama backend (the default)
```

## 5. Uninstall

```bash
./scripts/uninstall.sh            # keeps your data
./scripts/uninstall.sh --purge    # also removes ~/.local/share/aios
sudo rm -f /usr/share/wayland-sessions/aios.desktop
```

## Roadmap from here

The kiosk-browser shell is the MVP. Next in Phase 3: a native panel/launcher, a
global hotkey to summon the assistant as an overlay over other apps, and theming
— see [ROADMAP.md](../ROADMAP.md).
