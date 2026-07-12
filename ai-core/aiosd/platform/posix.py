"""POSIX implementation of the Platform HAL (Linux; macOS for development).

This is the one place in AIOS allowed to know about ``pmset`` vs ``/sys``,
``uname``, etc. Everything is best-effort and never raises, so callers above the
HAL can treat device facts as always-available (possibly "unknown").
"""

from __future__ import annotations

import getpass
import os
import platform as _platform
import shutil
import socket
import subprocess

from . import Platform


def _safe(fn, default: str = "unknown") -> str:
    try:
        return fn()
    except Exception:
        return default


class PosixPlatform(Platform):
    name = "posix"

    def hostname(self) -> str:
        return _safe(socket.gethostname)

    def username(self) -> str:
        return _safe(getpass.getuser)

    def os_description(self) -> str:
        return f"{_platform.system()} {_platform.release()} ({_platform.machine()})"

    def battery(self) -> str | None:
        return self._battery_macos() or self._battery_linux()

    # -- host-specific power sources (isolated here on purpose) -----------
    def _battery_macos(self) -> str | None:
        if not shutil.which("pmset"):
            return None
        try:
            out = subprocess.run(
                ["pmset", "-g", "batt"], capture_output=True, text=True, timeout=3
            )
        except Exception:
            return None
        for token in out.stdout.split():
            if token.endswith("%;"):
                return token.rstrip(";")
        return None

    def _battery_linux(self) -> str | None:
        base = "/sys/class/power_supply"
        try:
            names = sorted(os.listdir(base))
        except OSError:
            return None
        for name in names:
            capacity = os.path.join(base, name, "capacity")
            try:
                with open(capacity, encoding="utf-8") as fh:
                    return fh.read().strip() + "%"
            except OSError:
                continue
        return None
