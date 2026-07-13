"""UpdateManager — the AIOS seam over how the system updates itself.

Isolating this (Constitution §II; matrix row #20) means the *mechanism* of
updating is swappable. Today AIOS is deployed as a git checkout, so
`GitUpdateManager` reflects that stage: check the tracked branch and fast-forward
to it. When AIOS ships as an atomic image (Stage 3), an
`ImageUpdateManager`/ostree implementation slots in behind the same interface and
nothing above it changes.

Safety: `status()` is read-only. `apply()` refuses when the working tree is dirty
(never clobbers local changes) and only **fast-forwards** (never force-merges).
"""

from __future__ import annotations

import os
import subprocess
from abc import ABC, abstractmethod

from . import __version__


class UpdateManager(ABC):
    name = "base"

    @abstractmethod
    def status(self) -> dict:
        """Read-only: {ok, version, current, latest, behind, update_available, clean}."""

    @abstractmethod
    def apply(self) -> dict:
        """Apply an available update. Returns {ok, applied, from, to} or {ok: False, error}."""


class GitUpdateManager(UpdateManager):
    name = "git"

    def __init__(self, repo_dir: str, branch: str = "main", remote: str = "origin"):
        self.repo_dir = repo_dir
        self.branch = branch
        self.remote = remote

    def _git(self, *args, timeout: int = 30):
        return subprocess.run(["git", "-C", self.repo_dir, *args],
                              capture_output=True, text=True, timeout=timeout)

    def _is_repo(self) -> bool:
        r = self._git("rev-parse", "--is-inside-work-tree")
        return r.returncode == 0 and r.stdout.strip() == "true"

    def status(self, fetch: bool = True) -> dict:
        if not self._is_repo():
            return {"ok": False, "error": f"not a git checkout: {self.repo_dir}"}
        current = self._git("rev-parse", "HEAD").stdout.strip()
        clean = self._git("status", "--porcelain").stdout.strip() == ""
        if fetch:
            self._git("fetch", self.remote, self.branch, timeout=60)
        latest = self._git("rev-parse", f"{self.remote}/{self.branch}").stdout.strip()
        behind = 0
        if latest:
            count = self._git("rev-list", "--count",
                              f"HEAD..{self.remote}/{self.branch}").stdout.strip()
            behind = int(count) if count.isdigit() else 0
        return {"ok": True, "version": __version__, "repo": self.repo_dir,
                "branch": self.branch, "current": current[:12], "latest": latest[:12],
                "behind": behind, "update_available": behind > 0, "clean": clean}

    def apply(self) -> dict:
        st = self.status(fetch=True)
        if not st.get("ok"):
            return st
        if not st["clean"]:
            return {"ok": False,
                    "error": "working tree has uncommitted changes — commit or stash first"}
        if not st["update_available"]:
            return {"ok": True, "applied": False, "message": "already up to date",
                    "current": st["current"]}
        pull = self._git("pull", "--ff-only", self.remote, self.branch, timeout=120)
        if pull.returncode != 0:
            return {"ok": False,
                    "error": f"git pull failed: {(pull.stderr or pull.stdout).strip()}"}
        new = self._git("rev-parse", "HEAD").stdout.strip()
        return {"ok": True, "applied": True, "from": st["current"], "to": new[:12]}


def default_repo_dir() -> str:
    # this file is <repo>/ai-core/aiosd/update.py -> repo root is three levels up
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_update_manager(repo_dir: str | None = None, branch: str = "main") -> UpdateManager:
    return GitUpdateManager(repo_dir or default_repo_dir(), branch=branch)
