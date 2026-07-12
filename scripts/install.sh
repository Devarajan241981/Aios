#!/usr/bin/env bash
# install.sh — user-level install of AIOS: CLI, daemon service, and the desktop
# session. Idempotent. Supports --dry-run. Does not require root; the one
# system-level step (registering the login session) is printed for you to run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) echo "Usage: install.sh [--dry-run]"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[36m▶ %s\033[0m\n' "$*"; }
note() { printf '  %s\n' "$*"; }
run()  {
  if [ "$DRY_RUN" = 1 ]; then
    printf '  +'; printf ' %q' "$@"; printf '\n'
  else
    "$@"
  fi
}

BIN="$HOME/.local/bin"
CFG="$HOME/.config/aios"
UNIT_DIR="$HOME/.config/systemd/user"

say "Installing AIOS from $REPO"
run mkdir -p "$BIN" "$CFG/sway" "$UNIT_DIR"

say "CLI  → $BIN/aios"
run ln -sf "$REPO/bin/aios" "$BIN/aios"

say "Desktop helpers → $BIN/{aios-shell,aios-session,aios-overlay,aios-overlay-toggle}"
run install -m 0755 "$REPO/packaging/desktop/aios-shell"          "$BIN/aios-shell"
run install -m 0755 "$REPO/packaging/desktop/aios-session"        "$BIN/aios-session"
run install -m 0755 "$REPO/packaging/desktop/aios-overlay"        "$BIN/aios-overlay"
run install -m 0755 "$REPO/packaging/desktop/aios-overlay-toggle" "$BIN/aios-overlay-toggle"
run install -m 0755 "$REPO/packaging/desktop/aios-launch"         "$BIN/aios-launch"

say "Sway session config → $CFG/sway/config"
run install -m 0644 "$REPO/packaging/desktop/sway/config" "$CFG/sway/config"

say "Status line (swaybar) → $BIN/aios-statusline"
if [ "$DRY_RUN" = 1 ]; then
  note "+ generate aios-statusline wrapper (python3 -m aiosd.statusline, PYTHONPATH=$REPO/ai-core)"
else
  printf '#!/usr/bin/env bash\nexec env PYTHONPATH=%q python3 -m aiosd.statusline "$@"\n' \
      "$REPO/ai-core" > "$BIN/aios-statusline"
  chmod +x "$BIN/aios-statusline"
fi

say "systemd user service → $UNIT_DIR/aiosd.service"
if [ "$DRY_RUN" = 1 ]; then
  note "+ generate unit with WorkingDirectory=$REPO/ai-core"
else
  sed "s|^WorkingDirectory=.*|WorkingDirectory=$REPO/ai-core|" \
      "$REPO/packaging/systemd/aiosd.service" > "$UNIT_DIR/aiosd.service"
fi

if command -v systemctl >/dev/null 2>&1; then
  run systemctl --user daemon-reload
  run systemctl --user enable aiosd.service
  note "start now with:  systemctl --user start aiosd.service"
else
  note "systemd not found — start the daemon manually:"
  note "  (cd '$REPO/ai-core' && python3 -m aiosd)"
fi

echo
say "Almost done. Two things to check:"
note "1. Ensure ~/.local/bin is on your PATH:"
note "     export PATH=\"\$HOME/.local/bin:\$PATH\""
note "2. Register the AIOS login session (needs root):"
note "     sudo install -m 0644 '$REPO/packaging/desktop/aios.desktop' \\"
note "       /usr/share/wayland-sessions/aios.desktop"
echo
say "Then log out and pick 'AIOS' at the login screen — or just run: aios-session"
