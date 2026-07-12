"""ServiceManager — the AIOS seam over host service supervision & scheduling.

This is the boundary that isolates the host init/service system (systemd today)
from the rest of AIOS (Constitution §I, matrix row #12). **No AIOS component
above this seam may call ``systemctl`` or write a systemd unit directly.** They
depend on the :class:`ServiceManager` interface; the systemd knowledge lives only
in :class:`SystemdServiceManager`.

When AIOS gains its own init (`aiosinit`, Stage 2) or runs on its own kernel, a
new ``ServiceManager`` implementation is added and callers do not change.

The interface is intentionally two things a *future* init must also provide:
long-running **service lifecycle** and **scheduled jobs**. Nothing systemd-shaped
crosses it — jobs are described in AIOS-neutral terms (:class:`ScheduledJob`).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass

_WEEKDAYS = {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu",
             "fri": "Fri", "sat": "Sat", "sun": "Sun"}


@dataclass
class ScheduledJob:
    """A recurring job in AIOS-neutral terms. Adapters map it to their backend."""
    name: str
    when: str          # friendly schedule, e.g. "daily 08:00" / "hourly" / "mon 09:00"
    command: str       # absolute command/path to execute
    description: str = ""


class ServiceManager(ABC):
    name = "base"

    @property
    @abstractmethod
    def available(self) -> bool:
        """True if this manager can actuate the running system."""

    # -- long-running service lifecycle -----------------------------------
    @abstractmethod
    def start(self, service: str) -> bool: ...
    @abstractmethod
    def stop(self, service: str) -> bool: ...
    @abstractmethod
    def restart(self, service: str) -> bool: ...
    @abstractmethod
    def enable(self, service: str, start: bool = False) -> bool: ...
    @abstractmethod
    def disable(self, service: str, stop: bool = False) -> bool: ...
    @abstractmethod
    def is_active(self, service: str) -> str:
        """'active' | 'inactive' | 'unknown'."""
    @abstractmethod
    def reload(self) -> None:
        """Apply configuration changes (systemd: daemon-reload)."""

    # -- scheduled jobs ---------------------------------------------------
    @abstractmethod
    def schedule(self, job: ScheduledJob) -> dict:
        """Register a recurring job. Returns {'calendar', 'backend', 'enabled'}."""
    @abstractmethod
    def unschedule(self, name: str) -> bool:
        """Remove a scheduled job. True if it existed."""


# --- systemd formatting (adapter-private, kept pure for testing) ---------

def _is_time(s: str) -> bool:
    hh, sep, mm = s.partition(":")
    return bool(sep) and hh.isdigit() and mm.isdigit()


def _norm_time(s: str) -> str:
    hh, mm = s.split(":")[:2]
    return f"{int(hh):02d}:{int(mm):02d}:00"


def to_oncalendar(when: str) -> str:
    """Map a friendly schedule to a systemd OnCalendar string (or pass through)."""
    text = when.strip()
    low = text.lower()
    if low in ("hourly", "daily", "weekly", "monthly", "yearly"):
        return low
    parts = low.split()
    if len(parts) == 2 and parts[0][:3] in _WEEKDAYS and _is_time(parts[1]):
        return f"{_WEEKDAYS[parts[0][:3]]} *-*-* {_norm_time(parts[1])}"
    if len(parts) == 2 and parts[0] == "daily" and _is_time(parts[1]):
        return f"*-*-* {_norm_time(parts[1])}"
    if len(parts) == 1 and _is_time(parts[0]):
        return f"*-*-* {_norm_time(parts[0])}"
    return text


def service_unit(name: str, exec_command: str, description: str = "") -> str:
    desc = description or f"AIOS automation: {name}"
    return (f"[Unit]\nDescription={desc}\n\n"
            f"[Service]\nType=oneshot\nExecStart={exec_command}\n")


def timer_unit(name: str, oncalendar: str, description: str = "") -> str:
    desc = description or f"AIOS automation timer: {name}"
    return (f"[Unit]\nDescription={desc}\n\n"
            f"[Timer]\nOnCalendar={oncalendar}\nPersistent=true\n\n"
            f"[Install]\nWantedBy=timers.target\n")


class SystemdServiceManager(ServiceManager):
    """The only class in AIOS that knows systemd. Writes user units and, when
    ``systemctl`` is present, actuates them. On a host without systemd it still
    writes the unit files (so they can be inspected / carried to Linux)."""

    name = "systemd"

    def __init__(self, unit_dir: str, systemctl: str | None = None):
        self.unit_dir = unit_dir
        # None -> autodetect; "" -> explicitly disabled (tests / non-systemd host)
        self._systemctl = shutil.which("systemctl") if systemctl is None else systemctl

    @property
    def available(self) -> bool:
        return bool(self._systemctl)

    def _run(self, *args) -> None:
        if self._systemctl:
            subprocess.run([self._systemctl, "--user", *args], check=False)

    def start(self, service): self._run("start", service); return self.available
    def stop(self, service): self._run("stop", service); return self.available
    def restart(self, service): self._run("restart", service); return self.available

    def enable(self, service, start=False):
        self._run("enable", *(["--now"] if start else []), service)
        return self.available

    def disable(self, service, stop=False):
        self._run("disable", *(["--now"] if stop else []), service)
        return self.available

    def is_active(self, service):
        if not self._systemctl:
            return "unknown"
        result = subprocess.run([self._systemctl, "--user", "is-active", service],
                                capture_output=True, text=True)
        return result.stdout.strip() or "unknown"

    def reload(self):
        self._run("daemon-reload")

    def schedule(self, job: ScheduledJob) -> dict:
        os.makedirs(self.unit_dir, exist_ok=True)
        oncalendar = to_oncalendar(job.when)
        with open(self._path(job.name, "service"), "w", encoding="utf-8") as fh:
            fh.write(service_unit(job.name, job.command, job.description))
        with open(self._path(job.name, "timer"), "w", encoding="utf-8") as fh:
            fh.write(timer_unit(job.name, oncalendar))
        self.reload()
        self._run("enable", "--now", f"aios-{job.name}.timer")
        return {"calendar": oncalendar, "backend": "systemd", "enabled": self.available}

    def unschedule(self, name: str) -> bool:
        existed = os.path.exists(self._path(name, "timer"))
        self._run("disable", "--now", f"aios-{name}.timer")
        for kind in ("service", "timer"):
            try:
                os.remove(self._path(name, kind))
            except OSError:
                pass
        self.reload()
        return existed

    def _path(self, name: str, kind: str) -> str:
        return os.path.join(self.unit_dir, f"aios-{name}.{kind}")


class NullServiceManager(ServiceManager):
    """No-op manager for hosts with no supported service system."""

    name = "none"

    @property
    def available(self) -> bool:
        return False

    def start(self, service): return False
    def stop(self, service): return False
    def restart(self, service): return False
    def enable(self, service, start=False): return False
    def disable(self, service, stop=False): return False
    def is_active(self, service): return "unknown"
    def reload(self): pass
    def schedule(self, job): return {"calendar": job.when, "backend": "none", "enabled": False}
    def unschedule(self, name): return False


def current_service_manager(unit_dir: str | None = None) -> ServiceManager:
    """Select the host's service manager. systemd today; extended as AIOS grows."""
    if unit_dir is None:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
        unit_dir = os.path.join(base, "systemd", "user")
    return SystemdServiceManager(unit_dir)
