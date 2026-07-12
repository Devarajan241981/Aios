"""Local device-context provider.

Gathers a small, non-sensitive snapshot of machine state so the assistant is
grounded ("context-aware") the way an OS assistant should be.

All host facts are obtained through the Platform HAL (``aiosd.platform``) — this
module contains **no** OS-specific code. That is deliberate: when AIOS runs on a
different kernel, only the Platform implementation changes; this file does not.
See ``docs/architecture/01-layered-architecture.md``.

This is the seed of a richer context layer (open windows, active app, selected
text, semantic index) planned for later phases.
"""

from __future__ import annotations

import datetime

from .platform import current_platform


def _battery():
    """Battery percentage string or None. Kept for callers that import it."""
    return current_platform().battery()


def gather_context() -> dict:
    platform = current_platform()
    ctx = {
        "time": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "user": platform.username(),
        "host": platform.hostname(),
        "os": platform.os_description(),
    }
    battery = platform.battery()
    if battery is not None:
        ctx["battery"] = battery
    return ctx


def render_context(ctx: dict) -> str:
    return "\n".join(f"- {key}: {value}" for key, value in ctx.items())
