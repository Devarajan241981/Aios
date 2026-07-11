"""Runtime configuration for aiosd, sourced from environment variables.

All settings have safe local-first defaults so the daemon runs with zero setup,
including semantic search (the default embedder needs no model or network).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _truthy(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _data_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".local", "share", "aios")


def _default_index_path() -> str:
    return os.path.join(_data_dir(), "index.json")


def _default_db_path() -> str:
    return os.path.join(_data_dir(), "aios.db")


@dataclass(frozen=True)
class Config:
    host: str = "127.0.0.1"          # loopback only — never bind public by default
    port: int = 8765
    backend: str = "ollama"          # "ollama" | "mock"
    model: str = "llama3.2"
    ollama_url: str = "http://127.0.0.1:11434"
    request_timeout: float = 120.0

    # --- semantic memory (Phase 2) ---
    embeddings: str = "hashing"      # "hashing" (offline, default) | "ollama"
    embed_model: str = "nomic-embed-text"
    index_path: str = field(default_factory=_default_index_path)
    rag_enabled: bool = True
    rag_top_k: int = 4

    # --- persistence, tools, hardening (Phase 2.5) ---
    db_path: str = field(default_factory=_default_db_path)
    history_limit: int = 40          # max prior turns replayed from a session
    tools_enabled: bool = True
    allowed_roots: tuple = ()        # extra dirs tools may read/write (home always ok)
    allowed_commands: tuple = ()     # extra commands run_command may execute
    token: str = ""                  # if set, require Bearer auth on the API
    log_level: str = "INFO"
    max_body_bytes: int = 4_000_000  # reject oversized request bodies

    @classmethod
    def from_env(cls, env: dict | None = None) -> "Config":
        env = os.environ if env is None else env
        roots = env.get("AIOS_ALLOWED_ROOTS", "")
        allowed = tuple(p for p in (r.strip() for r in roots.split(os.pathsep)) if p)
        cmds = env.get("AIOS_ALLOWED_COMMANDS", "")
        allowed_cmds = tuple(c for c in cmds.replace(",", " ").split() if c)
        return cls(
            host=env.get("AIOS_HOST", cls.host),
            port=int(env.get("AIOS_PORT", cls.port)),
            backend=env.get("AIOS_BACKEND", cls.backend),
            model=env.get("AIOS_MODEL", cls.model),
            ollama_url=env.get("AIOS_OLLAMA_URL", cls.ollama_url).rstrip("/"),
            request_timeout=float(env.get("AIOS_TIMEOUT", cls.request_timeout)),
            embeddings=env.get("AIOS_EMBEDDINGS", cls.embeddings),
            embed_model=env.get("AIOS_EMBED_MODEL", cls.embed_model),
            index_path=env.get("AIOS_INDEX_PATH") or _default_index_path(),
            rag_enabled=_truthy(env.get("AIOS_RAG", "on")),
            rag_top_k=int(env.get("AIOS_RAG_TOPK", cls.rag_top_k)),
            db_path=env.get("AIOS_DB_PATH") or _default_db_path(),
            history_limit=int(env.get("AIOS_HISTORY_LIMIT", cls.history_limit)),
            tools_enabled=_truthy(env.get("AIOS_TOOLS", "on")),
            allowed_roots=allowed,
            allowed_commands=allowed_cmds,
            token=env.get("AIOS_TOKEN", cls.token),
            log_level=env.get("AIOS_LOG_LEVEL", cls.log_level).upper(),
            max_body_bytes=int(env.get("AIOS_MAX_BODY_BYTES", cls.max_body_bytes)),
        )
