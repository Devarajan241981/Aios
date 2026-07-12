#!/usr/bin/env bash
# asahi-bringup.sh — take a fresh Asahi Linux (Fedora Asahi Remix) install to a
# working AIOS desktop. Run as your normal user; it uses sudo for system
# packages. Supports --dry-run. Ollama and the AIOS install are the last steps.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) echo "Usage: asahi-bringup.sh [--dry-run]"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

say() { printf '\033[36m▶ %s\033[0m\n' "$*"; }
run() {
  if [ "$DRY_RUN" = 1 ]; then
    printf '  +'; printf ' %q' "$@"; printf '\n'
  else
    "$@"
  fi
}

if [ "$(uname -s)" != "Linux" ]; then
  echo "This script targets Asahi Linux (aarch64). Current OS: $(uname -s)." >&2
  echo "Run it on the MacBook after installing Fedora Asahi Remix." >&2
  [ "$DRY_RUN" = 1 ] || exit 1
fi

say "Installing system packages (Sway session, terminal, browser, tooling)"
if command -v dnf >/dev/null 2>&1; then
  run sudo dnf install -y sway foot firefox wofi python3 git curl
elif command -v apt-get >/dev/null 2>&1; then
  run sudo apt-get update
  run sudo apt-get install -y sway foot firefox-esr wofi python3 git curl
else
  echo "No supported package manager (dnf/apt). Install manually:" >&2
  echo "  sway foot firefox wofi python3 git curl" >&2
fi

say "Optional: install Ollama for on-device models"
echo "    curl -fsSL https://ollama.com/install.sh | sh"
echo "    ollama pull llama3.2"

say "Installing AIOS (user-level)"
if [ "$DRY_RUN" = 1 ]; then
  run "$SCRIPT_DIR/install.sh" --dry-run
else
  run "$SCRIPT_DIR/install.sh"
fi

say "Bring-up complete."
echo "Log out and choose the 'AIOS' session at the login screen,"
echo "or start it now from a TTY with:  aios-session"
