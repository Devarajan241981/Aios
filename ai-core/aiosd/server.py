"""Loopback HTTP server: assistant, semantic memory, tools, and sessions.

Endpoints:
    GET    /                    banner
    GET    /health              daemon + backend + index health
    GET    /version             version info
    POST   /v1/chat             {"prompt", "history"?, "session_id"?, "stream"?,
                                 "use_tools"?, "approve"?} -> reply (JSON or SSE)
    POST   /v1/index            {"paths": [...]} -> {"indexed", "documents"}
    GET    /v1/index/stats      -> {"documents", "sources"}
    POST   /v1/search           {"query", "k"?} -> {"results": [...]}
    GET    /v1/tools            -> {"enabled", "tools": [...]}
    GET    /v1/sessions         -> {"sessions": [...]}
    POST   /v1/sessions         {"title"?} -> created session
    GET    /v1/sessions/<id>    -> {"session", "messages"}
    DELETE /v1/sessions/<id>    -> {"deleted": bool}

Bound to 127.0.0.1. Threaded; a lock guards vector-store writes. Optional bearer
auth (AIOS_TOKEN) protects every endpoint except /health.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from .agent import Agent
from .assistant import Assistant
from .backends import Backend, BackendError, make_backend
from .config import Config
from .embeddings import Embedder, EmbeddingError, make_embedder
from .indexer import index_paths
from .retriever import Retriever
from .storage import Storage
from .store import VectorStore
from .tools import Registry, ToolContext, default_registry
from .ui import index_html

# Endpoints reachable without a bearer token: liveness and the static web app.
_PUBLIC_PATHS = {"/health", "/", "/favicon.ico"}

log = logging.getLogger("aiosd")


@dataclass
class AppState:
    config: Config
    backend: Backend
    embedder: Embedder
    vector_store: VectorStore
    retriever: object
    assistant: Assistant
    storage: Storage
    registry: Registry
    agent: Agent
    lock: threading.Lock


def _title_from(prompt: str) -> str:
    first_line = prompt.strip().splitlines()[0] if prompt.strip() else "New chat"
    return first_line[:48]


def make_handler(state: AppState):
    cfg = state.config

    class Handler(BaseHTTPRequestHandler):
        server_version = "aiosd/0.3"

        # -- low-level helpers --------------------------------------------
        def _json(self, code, payload):
            self._status = code
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html(self, text):
            self._status = 200
            body = text.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _sse_start(self):
            self._status = 200
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True

        def _sse(self, obj):
            self.wfile.write(f"data: {json.dumps(obj)}\n\n".encode())
            self.wfile.flush()

        def _body(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw or b"{}")

        def _auth_ok(self):
            if not cfg.token:
                return True
            return self.headers.get("Authorization", "") == f"Bearer {cfg.token}"

        def log_message(self, *args):
            pass  # request logging is handled explicitly in dispatch

        # -- dispatch with logging + auth ---------------------------------
        def do_GET(self):
            self._dispatch("GET", self._route_get)

        def do_POST(self):
            self._dispatch("POST", self._route_post)

        def do_DELETE(self):
            self._dispatch("DELETE", self._route_delete)

        def _dispatch(self, method, route):
            self._status = 200
            started = time.perf_counter()
            try:
                if self.path not in _PUBLIC_PATHS and not self._auth_ok():
                    self._json(401, {"error": "unauthorized"})
                    return
                route()
            except (ValueError, json.JSONDecodeError):
                self._json(400, {"error": "invalid JSON body"})
            except Exception as exc:  # last-resort guard
                log.exception("unhandled error")
                self._status = 500
                try:
                    self._json(500, {"error": f"internal error: {exc}"})
                except Exception:
                    pass
            finally:
                ms = (time.perf_counter() - started) * 1000
                log.info("%s %s -> %s (%.0fms)", method, self.path, self._status, ms)

        # -- routing ------------------------------------------------------
        def _route_get(self):
            if self.path == "/health":
                self._json(200, {
                    "status": "ok", "service": "aiosd", "version": __version__,
                    "backend": state.backend.health(),
                    "index": {"documents": len(state.vector_store),
                              "embeddings": state.embedder.name},
                    "tools": cfg.tools_enabled,
                })
            elif self.path == "/version":
                self._json(200, {"version": __version__,
                                 "python": platform.python_version()})
            elif self.path == "/v1/index/stats":
                self._json(200, {"documents": len(state.vector_store),
                                 "sources": state.vector_store.sources()})
            elif self.path == "/v1/tools":
                self._json(200, {"enabled": cfg.tools_enabled,
                                 "tools": state.registry.describe()})
            elif self.path == "/v1/sessions":
                self._json(200, {"sessions": state.storage.list_sessions()})
            elif self.path.startswith("/v1/sessions/"):
                self._get_session(self.path[len("/v1/sessions/"):])
            elif self.path == "/":
                self._html(index_html(__version__))
            elif self.path == "/favicon.ico":
                self._status = 204
                self.send_response(204)
                self.end_headers()
            else:
                self._json(404, {"error": "not found"})

        def _route_post(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > cfg.max_body_bytes:
                self._json(413, {"error": "request body too large"})
                return
            data = self._body()
            if self.path in ("/v1/chat", "/chat"):
                self._handle_chat(data)
            elif self.path == "/v1/index":
                self._handle_index(data)
            elif self.path == "/v1/search":
                self._handle_search(data)
            elif self.path == "/v1/sessions":
                sid = state.storage.create_session(title=data.get("title"))
                self._json(201, state.storage.get_session(sid))
            else:
                self._json(404, {"error": "not found"})

        def _route_delete(self):
            if self.path.startswith("/v1/sessions/"):
                sid = self.path[len("/v1/sessions/"):]
                self._json(200, {"deleted": state.storage.delete_session(sid)})
            else:
                self._json(404, {"error": "not found"})

        # -- session reads ------------------------------------------------
        def _get_session(self, sid):
            session = state.storage.get_session(sid)
            if session is None:
                self._json(404, {"error": "no such session"})
                return
            self._json(200, {"session": session,
                             "messages": state.storage.get_messages(sid)})

        # -- chat ---------------------------------------------------------
        def _handle_chat(self, data):
            prompt = (data.get("prompt") or data.get("message") or "").strip()
            if not prompt:
                self._json(400, {"error": "missing 'prompt'"})
                return

            session_id = data.get("session_id")
            use_tools = bool(data.get("use_tools")) and cfg.tools_enabled

            if session_id:
                history = state.storage.get_messages(session_id, limit=cfg.history_limit)
                first_turn = not history
            else:
                history = data.get("history") or []
                first_turn = False

            if data.get("stream") and not use_tools:
                self._stream_chat(prompt, history, session_id, first_turn)
                return

            try:
                if use_tools:
                    messages = state.assistant.build_messages(prompt, history)
                    result = state.agent.run(
                        messages,
                        approved=data.get("approved_signatures") or [],
                        approve_all=bool(data.get("approve")),
                    )
                    if result["status"] == "needs_approval":
                        # No side effects happened; caller must approve to proceed.
                        payload = {"status": "needs_approval",
                                   "pending": result["pending"],
                                   "steps": result["steps"], "model": cfg.model}
                        if session_id:
                            payload["session_id"] = session_id
                        self._json(200, payload)
                        return
                    reply, steps = result["reply"], result["steps"]
                else:
                    reply, steps = state.assistant.ask(prompt, history=history), []
            except (BackendError, EmbeddingError) as exc:
                self._json(502, {"error": str(exc)})
                return

            if session_id:
                self._persist_turn(session_id, prompt, reply, first_turn)

            payload = {"reply": reply, "model": cfg.model, "status": "complete"}
            if use_tools:
                payload["steps"] = steps
            if session_id:
                payload["session_id"] = session_id
            self._json(200, payload)

        def _stream_chat(self, prompt, history, session_id, first_turn):
            self._sse_start()
            parts = []
            try:
                for delta in state.assistant.ask_stream(prompt, history=history):
                    parts.append(delta)
                    self._sse({"delta": delta})
            except (BackendError, EmbeddingError) as exc:
                self._sse({"error": str(exc)})
            except Exception as exc:
                self._sse({"error": f"internal error: {exc}"})
            else:
                if session_id:
                    self._persist_turn(session_id, prompt, "".join(parts), first_turn)
                self._sse({"done": True, "model": cfg.model, "session_id": session_id})
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

        def _persist_turn(self, session_id, prompt, reply, first_turn):
            state.storage.add_message(session_id, "user", prompt)
            state.storage.add_message(session_id, "assistant", reply)
            if first_turn:
                state.storage.rename_session(session_id, _title_from(prompt))

        # -- semantic memory ----------------------------------------------
        def _handle_index(self, data):
            paths = data.get("paths")
            if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
                self._json(400, {"error": "'paths' must be a list of strings"})
                return
            try:
                with state.lock:
                    added = index_paths(paths, state.embedder, state.vector_store)
                    state.vector_store.save(cfg.index_path)
            except EmbeddingError as exc:
                self._json(502, {"error": str(exc)})
                return
            self._json(200, {"indexed": added, "documents": len(state.vector_store)})

        def _handle_search(self, data):
            query = (data.get("query") or "").strip()
            if not query:
                self._json(400, {"error": "missing 'query'"})
                return
            k = int(data.get("k", cfg.rag_top_k))
            try:
                query_vec = state.embedder.embed([query])[0]
            except EmbeddingError as exc:
                self._json(502, {"error": str(exc)})
                return
            self._json(200, {"results": state.vector_store.search(query_vec, k)})

    return Handler


def build_state(config) -> AppState:
    backend = make_backend(config)
    embedder = make_embedder(config)

    vector_store = VectorStore()
    if config.index_path and os.path.exists(config.index_path):
        vector_store.load(config.index_path)

    retriever = (
        Retriever(vector_store, embedder, config.rag_top_k)
        if config.rag_enabled else None
    )
    assistant = Assistant(backend, config, retriever=retriever)
    storage = Storage(config.db_path)
    registry = default_registry()
    tool_ctx = ToolContext(config=config, retriever=retriever)
    agent = Agent(backend, registry, tool_ctx, config)

    return AppState(
        config=config, backend=backend, embedder=embedder,
        vector_store=vector_store, retriever=retriever, assistant=assistant,
        storage=storage, registry=registry, agent=agent, lock=threading.Lock(),
    )


def build_server(config) -> ThreadingHTTPServer:
    state = build_state(config)
    httpd = ThreadingHTTPServer((config.host, config.port), make_handler(state))
    httpd.aios_state = state  # exposed so callers/tests can close resources
    return httpd


def serve(config=None):
    config = config or Config.from_env()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    httpd = build_server(config)
    host, port = httpd.server_address
    log.info(
        "aiosd %s listening on http://%s:%s (backend=%s, model=%s, "
        "embeddings=%s, rag=%s, tools=%s, auth=%s)",
        __version__, host, port, config.backend, config.model, config.embeddings,
        "on" if config.rag_enabled else "off",
        "on" if config.tools_enabled else "off",
        "on" if config.token else "off",
    )
    print(f"aiosd {__version__} listening on http://{host}:{port}", flush=True)
    print(f"  web UI:  http://{host}:{port}/", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\naiosd shutting down")
    finally:
        httpd.server_close()
        httpd.aios_state.storage.close()
