"""Append-only audit log of tool activity.

Every tool the assistant executes — and every mutating action it pauses on for
approval — is recorded as one JSON object per line in a local file
(``~/.local/share/aios/audit.log`` by default). This is the observability and
trust layer over the tool system: you can always see what the AI did on your
machine.

Writing is best-effort and must never break a request; long string arguments
(e.g. file contents) are summarized rather than stored in full.
"""

from __future__ import annotations

import json
import os
import threading
import time

_MAX_STR = 120


def _summarize(value):
    if isinstance(value, str) and len(value) > _MAX_STR:
        return value[:_MAX_STR] + f"… ({len(value)} chars)"
    return value


def summarize_args(args):
    if not isinstance(args, dict):
        return args
    return {k: _summarize(v) for k, v in args.items()}


class AuditLog:
    def __init__(self, path: str, enabled: bool = True):
        self.path = path
        self.enabled = enabled and bool(path)
        self._lock = threading.Lock()

    def record(self, event: dict) -> None:
        if not self.enabled:
            return
        line = json.dumps({"ts": time.time(), **event})
        try:
            with self._lock:
                directory = os.path.dirname(self.path)
                if directory:
                    os.makedirs(directory, exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except OSError:
            pass  # auditing must never break a request

    def tail(self, n: int = 50):
        if not self.path or not os.path.exists(self.path):
            return []
        try:
            with self._lock, open(self.path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except OSError:
            return []
        events = []
        for line in lines[-n:]:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
        return events
