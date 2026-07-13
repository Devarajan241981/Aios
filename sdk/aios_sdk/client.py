"""AIOSClient — the developer-facing client for the AIOS Platform API v1.

Apps target *AIOS*, not raw HTTP. Zero dependencies (stdlib only). Every method
maps to a `/v1` endpoint documented in
docs/architecture/04-platform-api-v1.md; the SDK is versioned to that contract.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .errors import AIOSConnectionError, APIError
from .models import ChatResult, Notification, SearchResult, Session

API_VERSION = 1


class AIOSClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8765",
                 token: str | None = None, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    # -- transport --------------------------------------------------------
    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _open(self, method, path, payload=None, timeout=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method,
                                     headers=self._headers())
        try:
            return urllib.request.urlopen(req, timeout=timeout or self.timeout)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            try:
                message = json.loads(body).get("error", body)
            except ValueError:
                message = body
            raise APIError(exc.code, message) from exc
        except urllib.error.URLError as exc:
            raise AIOSConnectionError(
                f"cannot reach aiosd at {self.base_url}: {exc.reason}") from exc

    def _request(self, method, path, payload=None, timeout=None):
        with self._open(method, path, payload, timeout) as resp:
            return json.loads(resp.read().decode())

    # -- operations plane -------------------------------------------------
    def health(self) -> dict:
        return self._request("GET", "/health")

    def version(self) -> dict:
        return self._request("GET", "/version")

    # -- chat -------------------------------------------------------------
    def ask(self, prompt: str, *, session: str | None = None, history=None,
            use_tools: bool = False, approve: bool = False,
            approved_signatures=None) -> ChatResult:
        payload: dict = {"prompt": prompt}
        if session:
            payload["session_id"] = session
        elif history is not None:
            payload["history"] = history
        if use_tools:
            payload["use_tools"] = True
        if approve:
            payload["approve"] = True
        if approved_signatures:
            payload["approved_signatures"] = list(approved_signatures)
        return ChatResult.from_dict(self._request("POST", "/v1/chat", payload, timeout=600))

    def stream(self, prompt: str, *, session: str | None = None, history=None):
        """Yield reply text deltas as they arrive (SSE)."""
        payload: dict = {"prompt": prompt, "stream": True}
        if session:
            payload["session_id"] = session
        elif history is not None:
            payload["history"] = history
        with self._open("POST", "/v1/chat", payload, timeout=600) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                if not line.startswith("data:"):
                    continue
                body = line[len("data:"):].strip()
                if body == "[DONE]":
                    break
                try:
                    event = json.loads(body)
                except ValueError:
                    continue
                if "delta" in event:
                    yield event["delta"]
                elif "error" in event:
                    raise APIError(502, event["error"])

    # -- semantic memory --------------------------------------------------
    def index(self, paths) -> dict:
        return self._request("POST", "/v1/index", {"paths": list(paths)}, timeout=600)

    def index_stats(self) -> dict:
        return self._request("GET", "/v1/index/stats")

    def search(self, query: str, k: int = 5) -> list:
        res = self._request("POST", "/v1/search", {"query": query, "k": k})
        return [SearchResult(r["source"], r["text"], r["score"]) for r in res["results"]]

    # -- tools ------------------------------------------------------------
    def tools(self) -> list:
        return self._request("GET", "/v1/tools")["tools"]

    # -- sessions ---------------------------------------------------------
    def sessions(self) -> list:
        return [Session.from_dict(s) for s in self._request("GET", "/v1/sessions")["sessions"]]

    def create_session(self, title: str | None = None) -> Session:
        return Session.from_dict(
            self._request("POST", "/v1/sessions", {"title": title} if title else {}))

    def session(self, session_id: str) -> dict:
        return self._request("GET", f"/v1/sessions/{session_id}")

    def delete_session(self, session_id: str) -> bool:
        return self._request("DELETE", f"/v1/sessions/{session_id}").get("deleted", False)

    def grant(self, session_id: str, tool: str) -> list:
        return self._request("POST", f"/v1/sessions/{session_id}/grants",
                             {"tool": tool})["grants"]

    def revoke(self, session_id: str, tool: str) -> list:
        return self._request("POST", f"/v1/sessions/{session_id}/grants",
                             {"tool": tool, "revoke": True})["grants"]

    # -- notifications ----------------------------------------------------
    def notify(self, title: str, body: str = "", level: str = "info",
               source: str = "sdk") -> Notification:
        return Notification.from_dict(self._request(
            "POST", "/v1/notifications",
            {"title": title, "body": body, "level": level, "source": source}))

    def notifications(self, unread: bool = False, n: int = 50):
        path = f"/v1/notifications?n={n}" + ("&unread=1" if unread else "")
        d = self._request("GET", path)
        return [Notification.from_dict(x) for x in d["notifications"]], d["unread"]

    def mark_read(self, notification_id: str | None = None) -> dict:
        return self._request("POST", "/v1/notifications/read",
                             {"id": notification_id} if notification_id else {})

    def clear_notifications(self) -> int:
        return self._request("DELETE", "/v1/notifications").get("cleared", 0)

    # -- audit ------------------------------------------------------------
    def audit(self, n: int = 50) -> list:
        return self._request("GET", f"/v1/audit?n={n}")["events"]
