"""Conversation persistence.

A small, thread-safe SQLite store for chat sessions and their messages so the
assistant remembers context across restarts. Stdlib ``sqlite3`` only; the file
lives under the user's data dir and never leaves the machine.

The daemon is threaded, so every method serializes access through a lock and a
single shared connection opened with ``check_same_thread=False``.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
import uuid

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
"""

DEFAULT_TITLE = "New chat"


class Storage:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        if path != ":memory:":
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- sessions ---------------------------------------------------------
    def create_session(self, title: str | None = None, session_id: str | None = None) -> str:
        sid = session_id or uuid.uuid4().hex[:12]
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO sessions(id, title, created_at, updated_at) "
                "VALUES(?, ?, ?, ?)",
                (sid, title or DEFAULT_TITLE, now, now),
            )
            self._conn.commit()
        return sid

    def rename_session(self, session_id: str, title: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET title=? WHERE id=?", (title, session_id)
            )
            self._conn.commit()

    def get_session(self, session_id: str):
        with self._lock:
            row = self._conn.execute(
                "SELECT id, title, created_at, updated_at FROM sessions WHERE id=?",
                (session_id,),
            ).fetchone()
            count = self._conn.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id=?", (session_id,)
            ).fetchone()[0]
        if row is None:
            return None
        return {
            "id": row[0], "title": row[1],
            "created_at": row[2], "updated_at": row[3], "messages": count,
        }

    def list_sessions(self):
        with self._lock:
            rows = self._conn.execute(
                "SELECT s.id, s.title, s.created_at, s.updated_at, "
                "  (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) "
                "FROM sessions s ORDER BY s.updated_at DESC"
            ).fetchall()
        return [
            {"id": r[0], "title": r[1], "created_at": r[2],
             "updated_at": r[3], "messages": r[4]}
            for r in rows
        ]

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
            self._conn.commit()
            return cur.rowcount > 0

    # -- messages ---------------------------------------------------------
    def add_message(self, session_id: str, role: str, content: str) -> None:
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO sessions(id, title, created_at, updated_at) "
                "VALUES(?, ?, ?, ?)",
                (session_id, DEFAULT_TITLE, now, now),
            )
            self._conn.execute(
                "INSERT INTO messages(session_id, role, content, created_at) "
                "VALUES(?, ?, ?, ?)",
                (session_id, role, content, now),
            )
            self._conn.execute(
                "UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id)
            )
            self._conn.commit()

    def get_messages(self, session_id: str, limit: int | None = None):
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, content FROM messages WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        messages = [{"role": r[0], "content": r[1]} for r in rows]
        if limit is not None:
            messages = messages[-limit:]
        return messages

    def close(self) -> None:
        with self._lock:
            self._conn.close()
