"""AIOS status line for swaybar (the i3bar JSON protocol).

Emits a stream of status blocks — an AIOS button, backend state, index size,
battery, and clock — and, because ``click_events`` is enabled, launches the
assistant overlay when the AIOS block is clicked.

Run as ``python3 -m aiosd.statusline``; the desktop install wires this up as the
Sway session's ``status_command``. The block-building logic is pure and unit
tested; only ``main`` does I/O.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

from .context import _battery

ACCENT = "#7c74ff"
MUTED = "#9a9aa6"
OFF = "#e05a5a"


def fetch_health(base_url: str, timeout: float = 2.0) -> dict:
    """Best-effort GET /health. Returns {} if the daemon is unreachable."""
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/health", timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return {}


def render_blocks(health: dict, when: datetime.datetime, batt: str | None) -> list[dict]:
    """Build the i3bar block list. Pure — no I/O."""
    blocks = [{"name": "aios", "full_text": " AIOS ",
               "color": "#ffffff", "background": ACCENT if health else MUTED}]

    backend = health.get("backend") or {}
    if not health:
        blocks.append({"name": "backend", "full_text": "daemon offline", "color": OFF})
    else:
        name = backend.get("backend", "?")
        ok = backend.get("ok", True)
        blocks.append({
            "name": "backend",
            "full_text": name if ok else f"{name} (offline)",
            "color": None if ok else OFF,
        })
        docs = (health.get("index") or {}).get("documents")
        if docs is not None:
            blocks.append({"name": "index", "full_text": f"{docs} docs", "color": MUTED})

    if batt:
        blocks.append({"name": "battery", "full_text": f"bat {batt}", "color": MUTED})

    blocks.append({"name": "clock", "full_text": when.strftime("%a %d %b  %H:%M")})

    # i3bar rejects null keys; drop them.
    return [{k: v for k, v in b.items() if v is not None} for b in blocks]


def _click_loop():
    launcher = shutil.which("aios-overlay-toggle") or "aios-overlay-toggle"
    for raw in sys.stdin:
        text = raw.strip().lstrip("[,").strip()
        if not text:
            continue
        try:
            event = json.loads(text)
        except ValueError:
            continue
        if event.get("name") == "aios":
            try:
                subprocess.Popen([launcher])
            except Exception:
                pass


def main() -> int:
    port = os.environ.get("AIOS_PORT", "8765")
    base_url = os.environ.get("AIOS_URL", f"http://127.0.0.1:{port}")
    interval = float(os.environ.get("AIOS_STATUS_INTERVAL", "5"))

    sys.stdout.write(json.dumps({"version": 1, "click_events": True}) + "\n[\n")
    sys.stdout.flush()
    threading.Thread(target=_click_loop, daemon=True).start()

    first = True
    try:
        while True:
            blocks = render_blocks(fetch_health(base_url), datetime.datetime.now(), _battery())
            sys.stdout.write(("" if first else ",") + json.dumps(blocks) + "\n")
            sys.stdout.flush()
            first = False
            time.sleep(interval)
    except (BrokenPipeError, KeyboardInterrupt):
        return 0  # swaybar closed the pipe or we were interrupted — exit quietly


if __name__ == "__main__":
    raise SystemExit(main())
