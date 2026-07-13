"""Typed return values for the AIOS SDK.

Lightweight dataclasses over the Platform API v1 JSON shapes. Unknown/extra
fields are ignored, so the SDK keeps working as the API grows additively.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SearchResult:
    source: str
    text: str
    score: float


@dataclass
class Session:
    id: str
    title: str
    created_at: float
    updated_at: float
    messages: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        return cls(d["id"], d.get("title", ""), d.get("created_at", 0.0),
                   d.get("updated_at", 0.0), d.get("messages", 0))


@dataclass
class Notification:
    id: str
    title: str
    body: str
    level: str
    source: str
    ts: float
    read: bool

    @classmethod
    def from_dict(cls, d: dict) -> "Notification":
        return cls(d.get("id", ""), d.get("title", ""), d.get("body", ""),
                   d.get("level", "info"), d.get("source", ""), d.get("ts", 0.0),
                   d.get("read", False))


@dataclass
class ChatResult:
    """A `/v1/chat` result — either a completed reply or a pending approval."""

    status: str
    reply: str = ""
    model: str = ""
    steps: list = field(default_factory=list)
    pending: list = field(default_factory=list)
    session_id: str | None = None

    @property
    def needs_approval(self) -> bool:
        return self.status == "needs_approval"

    @property
    def signatures(self) -> list:
        """Content-hash signatures of the pending actions (to approve)."""
        return [p.get("signature") for p in self.pending]

    @classmethod
    def from_dict(cls, d: dict) -> "ChatResult":
        return cls(status=d.get("status", "complete"), reply=d.get("reply", ""),
                   model=d.get("model", ""), steps=d.get("steps") or [],
                   pending=d.get("pending") or [], session_id=d.get("session_id"))
