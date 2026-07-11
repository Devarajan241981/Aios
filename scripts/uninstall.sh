#!/usr/bin/env bash
# uninstall.sh — remove the user-level AIOS install created by install.sh.
# Leaves your data (~/.local/share/aios) untouched unless --purge is given.
set -euo pipefail

DRY_RUN=0
PURGE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --purge)   PURGE=1 ;;
    -h|--help) echo "Usage: uninstall.sh [--dry-run] [--purge]"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

run() {
  if [ "$DRY_RUN" = 1 ]; then
    printf '  +'; printf ' %q' "$@"; printf '\n'
  else
    "$@"
  fi
}

BIN="$HOME/.local/bin"
CFG="$HOME/.config/aios"
UNIT_DIR="$HOME/.config/systemd/user"

if command -v systemctl >/dev/null 2>&1; then
  run systemctl --user disable --now aiosd.service || true
fi

run rm -f "$BIN/aios" "$BIN/aios-shell" "$BIN/aios-session" \
          "$BIN/aios-overlay" "$BIN/aios-overlay-toggle" "$BIN/aios-statusline"
run rm -f "$UNIT_DIR/aiosd.service"
run rm -rf "$CFG"

if command -v systemctl >/dev/null 2>&1; then
  run systemctl --user daemon-reload || true
fi

if [ "$PURGE" = 1 ]; then
  run rm -rf "$HOME/.local/share/aios"
  echo "purged data directory (~/.local/share/aios)"
else
  echo "kept your data in ~/.local/share/aios (use --purge to remove)"
fi

echo "AIOS uninstalled. Remove the login session with:"
echo "  sudo rm -f /usr/share/wayland-sessions/aios.desktop"
