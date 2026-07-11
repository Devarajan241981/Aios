"""Model backends for aiosd.

A backend turns a list of chat messages into a reply. Two are provided:

* ``OllamaBackend`` — talks to a local Ollama server via its OpenAI-compatible
  ``/v1/chat/completions`` endpoint. The same code path works against
  llama.cpp-server or LocalAI, which expose the same API.
* ``MockBackend`` — deterministic, offline, dependency-free. Used by the test
  suite and as a fallback so the daemon is always demonstrable.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request


class BackendError(RuntimeError):
    """Raised when a backend cannot produce a reply (network, bad response...)."""


class Backend:
    name = "base"

    def chat(self, messages, *, model, timeout):  # pragma: no cover - interface
        raise NotImplementedError

    def stream_chat(self, messages, *, model, timeout):
        """Yield reply text deltas. Default: one delta with the full reply."""
        yield self.chat(messages, model=model, timeout=timeout)

    def chat_with_tools(self, messages, tools, *, model, timeout):
        """Return {"content", "tool_calls"}. Default: answer, no tool use."""
        return {"content": self.chat(messages, model=model, timeout=timeout), "tool_calls": []}

    def health(self):  # pragma: no cover - interface
        raise NotImplementedError


class MockBackend(Backend):
    """Offline backend that echoes the last user turn. Always healthy."""

    name = "mock"

    def chat(self, messages, *, model, timeout):
        last_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        return f"[mock:{model}] {last_user.strip()}"

    def stream_chat(self, messages, *, model, timeout):
        # Emit word-by-word so streaming is observable; deltas rejoin to chat().
        text = self.chat(messages, model=model, timeout=timeout)
        for i, word in enumerate(text.split(" ")):
            yield (" " + word) if i else word

    def health(self):
        return {"ok": True, "backend": self.name, "detail": "mock backend always available"}


class OllamaBackend(Backend):
    name = "ollama"

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _post(self, path, payload, timeout):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            raise BackendError(f"ollama HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise BackendError(
                f"cannot reach ollama at {self.base_url}: {exc.reason}. "
                "Is it running? Start it with `ollama serve`."
            ) from exc

    def chat(self, messages, *, model, timeout):
        payload = {"model": model, "messages": messages, "stream": False}
        out = self._post("/v1/chat/completions", payload, timeout)
        try:
            return out["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise BackendError(f"unexpected ollama response shape: {out!r}") from exc

    def stream_chat(self, messages, *, model, timeout):
        payload = {"model": model, "messages": messages, "stream": True}
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            raise BackendError(f"ollama HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise BackendError(
                f"cannot reach ollama at {self.base_url}: {exc.reason}. "
                "Is it running? Start it with `ollama serve`."
            ) from exc

        with resp:
            for raw in resp:  # Server-Sent Events: `data: {json}` lines
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                body = line[len("data:"):].strip()
                if body == "[DONE]":
                    break
                try:
                    obj = json.loads(body)
                    delta = obj["choices"][0]["delta"].get("content")
                except (ValueError, KeyError, IndexError, TypeError):
                    continue
                if delta:
                    yield delta

    @staticmethod
    def _to_openai(messages):
        """Translate the agent's normalized messages into OpenAI wire format."""
        out = []
        for m in messages:
            role = m.get("role")
            if role == "assistant" and m.get("tool_calls"):
                out.append({
                    "role": "assistant",
                    "content": m.get("content") or "",
                    "tool_calls": [
                        {"id": c["id"], "type": "function",
                         "function": {"name": c["name"],
                                      "arguments": json.dumps(c.get("arguments") or {})}}
                        for c in m["tool_calls"]
                    ],
                })
            elif role == "tool":
                out.append({"role": "tool",
                            "tool_call_id": m.get("tool_call_id"),
                            "content": m.get("content", "")})
            else:
                out.append({"role": role, "content": m.get("content", "")})
        return out

    def chat_with_tools(self, messages, tools, *, model, timeout):
        payload = {
            "model": model,
            "messages": self._to_openai(messages),
            "tools": tools,
            "stream": False,
        }
        out = self._post("/v1/chat/completions", payload, timeout)
        try:
            message = out["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise BackendError(f"unexpected ollama response shape: {out!r}") from exc

        tool_calls = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function", {})
            raw_args = fn.get("arguments")
            if isinstance(raw_args, str):
                try:
                    raw_args = json.loads(raw_args or "{}")
                except ValueError:
                    raw_args = {}
            tool_calls.append({
                "id": tc.get("id") or fn.get("name"),
                "name": fn.get("name"),
                "arguments": raw_args or {},
            })
        return {"content": message.get("content"), "tool_calls": tool_calls}

    def health(self):
        req = urllib.request.Request(self.base_url + "/api/tags", method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                tags = json.loads(resp.read().decode())
            models = [m.get("name") for m in tags.get("models", [])]
            return {"ok": True, "backend": self.name, "models": models}
        except Exception as exc:  # health must never raise
            return {
                "ok": False,
                "backend": self.name,
                "detail": f"{exc} (run `ollama serve` and `ollama pull <model>`)",
            }


def make_backend(config) -> Backend:
    if config.backend == "mock":
        return MockBackend()
    if config.backend == "ollama":
        return OllamaBackend(config.ollama_url)
    raise BackendError(f"unknown backend: {config.backend!r} (expected 'ollama' or 'mock')")
