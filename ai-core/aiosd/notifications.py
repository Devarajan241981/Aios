"""Notification center — an AIOS-owned service for surfacing messages to the user.

A net-new AIOS subsystem (matrix row #18, ADR-0010). Notifications are created by
AIOS components — the agent when it performs an action, scheduled automations via
`aios notify`, apps via the API — then stored locally and delivered through
channels.

The `NotificationChannel` seam isolates *how* a notification reaches the user:
- **in-app**: stored and polled by the web UI / CLI (always available, ours);
- **desktop**: freedesktop `notify-send` (host-specific, optional — degrades to a
  no-op where it isn't present, e.g. macOS during development).

Persistence is a local JSON file (low volume), consistent with the vector index
and the automations index. Thread-safe for the daemon.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from abc import ABC, abstractmethod

LEVELS = ("info", "success", "warning", "error")


class NotificationChannel(ABC):
    @abstractmethod
    def deliver(self, notification: dict) -> None:
        """Surface a notification. Must never raise."""


class DesktopChannel(NotificationChannel):
    """Delivers via freedesktop `notify-send` when it is available."""

    _URGENCY = {"error": "critical", "warning": "normal", "success": "normal", "info": "low"}

    def __init__(self):
        self._bin = shutil.which("notify-send")

    @property
    def available(self) -> bool:
        return bool(self._bin)

    def deliver(self, notification: dict) -> None:
        if not self._bin:
            return
        urgency = self._URGENCY.get(notification.get("level"), "normal")
        try:
            subprocess.run(
                [self._bin, "-a", "AIOS", "-u", urgency,
                 notification.get("title", "AIOS"), notification.get("body", "")],
                check=False, timeout=5,
            )
        except Exception:
            pass


class NotificationCenter:
    def __init__(self, path: str, channels=(), max_keep: int = 500):
        self.path = path
        self.channels = list(channels)
        self.max_keep = max_keep
        self._lock = threading.Lock()
        self._items = self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> list:
        if not self.path or not os.path.exists(self.path):
            return []
        try:
            with open(self.path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return []

    def _save(self) -> None:
        if not self.path:
            return
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._items, fh)
        os.replace(tmp, self.path)

    # -- operations -------------------------------------------------------
    def notify(self, title: str, body: str = "", level: str = "info",
               source: str = "aios") -> dict:
        if level not in LEVELS:
            level = "info"
        notification = {"id": uuid.uuid4().hex[:12], "title": title, "body": body,
                        "level": level, "source": source, "ts": time.time(),
                        "read": False}
        with self._lock:
            self._items.append(notification)
            if len(self._items) > self.max_keep:
                self._items = self._items[-self.max_keep:]
            self._save()
        for channel in self.channels:  # delivery must never fail the caller
            try:
                channel.deliver(notification)
            except Exception:
                pass
        return notification

    def list(self, unread_only: bool = False, limit: int = 50) -> list:
        with self._lock:
            items = [n for n in self._items if not unread_only or not n.get("read")]
        return list(reversed(items))[:limit]  # newest first

    def unread_count(self) -> int:
        with self._lock:
            return sum(1 for n in self._items if not n.get("read"))

    def mark_read(self, notification_id: str) -> bool:
        with self._lock:
            for n in self._items:
                if n["id"] == notification_id:
                    n["read"] = True
                    self._save()
                    return True
            return False

    def mark_all_read(self) -> int:
        with self._lock:
            count = sum(1 for n in self._items if not n.get("read"))
            for n in self._items:
                n["read"] = True
            if count:
                self._save()
            return count

    def clear(self) -> int:
        with self._lock:
            count = len(self._items)
            self._items = []
            self._save()
            return count
