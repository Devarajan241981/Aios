"""Local device-context provider.

Gathers a small, non-sensitive snapshot of the machine state so the assistant is
grounded ("context-aware") the way an OS assistant should be. Everything here is
best-effort and must never raise — a missing signal simply drops out.

This is the seed of a richer context layer (open windows, active app, selected
text, semantic index) planned for later phases.
"""

from __future__ import annotations

import datetime
import getpass
import platform
import shutil
import socket
import subprocess


def _safe(fn, default="unknown"):
    try:
        return fn()
    except Exception:
        return default


def _battery():
    """Return a battery percentage string, or None. macOS via pmset; Linux via sysfs."""
    if shutil.which("pmset"):
        try:
            out = subprocess.run(
                ["pmset", "-g", "batt"], capture_output=True, text=True, timeout=3
            )
            for token in out.stdout.split():
                if token.endswith("%;"):
                    return token.rstrip(";")
        except Exception:
            return None
    return None


def gather_context() -> dict:
    ctx = {
        "time": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "user": _safe(getpass.getuser),
        "host": _safe(socket.gethostname),
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
    }
    battery = _battery()
    if battery is not None:
        ctx["battery"] = battery
    return ctx


def render_context(ctx: dict) -> str:
    return "\n".join(f"- {key}: {value}" for key, value in ctx.items())
