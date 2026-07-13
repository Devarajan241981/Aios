"""PackageManager — the AIOS seam over installing applications.

Isolating this (Constitution §II; matrix row #19) means the app-distribution
mechanism is swappable. On the target base (Fedora Asahi) the mechanism is
**Flatpak**, so `FlatpakPackageManager` is the current implementation. A future
AIOS package/store service slots in behind the same interface.

Honesty note: Flatpak cannot run on the macOS development host, so the parsing
and the graceful-degradation paths are unit-tested here; command *execution* is
validated on the Linux target. The pure `_parse_columns` helper keeps the
testable logic separate from the subprocess call.
"""

from __future__ import annotations

import shutil
import subprocess
from abc import ABC, abstractmethod


def _parse_columns(output: str, keys) -> list:
    """Parse tab-separated `flatpak --columns=...` output into dicts. Pure."""
    rows = []
    for line in output.splitlines():
        line = line.rstrip()
        if not line:
            continue
        parts = line.split("\t")
        rows.append({k: (parts[i].strip() if i < len(parts) else "")
                     for i, k in enumerate(keys)})
    return rows


class PackageManager(ABC):
    name = "base"

    @property
    @abstractmethod
    def available(self) -> bool: ...
    @abstractmethod
    def list_installed(self) -> dict: ...
    @abstractmethod
    def search(self, query: str) -> dict: ...
    @abstractmethod
    def install(self, app_id: str) -> dict: ...
    @abstractmethod
    def remove(self, app_id: str) -> dict: ...


class FlatpakPackageManager(PackageManager):
    name = "flatpak"

    def __init__(self, flatpak: str | None = None, remote: str = "flathub"):
        # None -> autodetect; "" -> explicitly disabled (tests / non-flatpak host)
        self._bin = shutil.which("flatpak") if flatpak is None else flatpak
        self.remote = remote

    @property
    def available(self) -> bool:
        return bool(self._bin)

    def _run(self, *args, timeout: int = 60):
        return subprocess.run([self._bin, *args], capture_output=True, text=True, timeout=timeout)

    def _unavailable(self) -> dict:
        return {"ok": False, "error": "flatpak is not installed"}

    def list_installed(self) -> dict:
        if not self._bin:
            return self._unavailable()
        r = self._run("list", "--app", "--columns=application,name,version")
        if r.returncode != 0:
            return {"ok": False, "error": r.stderr.strip() or "flatpak list failed"}
        return {"ok": True, "apps": _parse_columns(r.stdout, ["id", "name", "version"])}

    def search(self, query: str) -> dict:
        if not self._bin:
            return self._unavailable()
        if not (query or "").strip():
            return {"ok": False, "error": "a search query is required"}
        r = self._run("search", "--columns=application,name,description", query)
        if r.returncode != 0:
            return {"ok": False, "error": r.stderr.strip() or "flatpak search failed"}
        return {"ok": True, "results": _parse_columns(r.stdout, ["id", "name", "description"])}

    def install(self, app_id: str) -> dict:
        if not self._bin:
            return self._unavailable()
        if not (app_id or "").strip():
            return {"ok": False, "error": "an application id is required"}
        r = self._run("install", "-y", self.remote, app_id, timeout=1200)
        if r.returncode != 0:
            return {"ok": False, "error": (r.stderr or r.stdout).strip()}
        return {"ok": True, "installed": app_id}

    def remove(self, app_id: str) -> dict:
        if not self._bin:
            return self._unavailable()
        if not (app_id or "").strip():
            return {"ok": False, "error": "an application id is required"}
        r = self._run("uninstall", "-y", app_id, timeout=300)
        if r.returncode != 0:
            return {"ok": False, "error": (r.stderr or r.stdout).strip()}
        return {"ok": True, "removed": app_id}


class NullPackageManager(PackageManager):
    name = "none"

    @property
    def available(self) -> bool:
        return False

    def _no(self):
        return {"ok": False, "error": "no package manager available"}

    def list_installed(self): return self._no()
    def search(self, query): return self._no()
    def install(self, app_id): return self._no()
    def remove(self, app_id): return self._no()


def make_package_manager(config=None) -> PackageManager:
    """Select the package manager. Flatpak on the target; self-degrades if absent."""
    return FlatpakPackageManager()
