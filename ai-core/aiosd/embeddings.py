"""Embedding backends for semantic search.

Two implementations, same interface (``embed(texts) -> list[list[float]]``,
returning L2-normalized vectors so cosine similarity is a plain dot product):

* ``HashingEmbedder`` — pure-Python feature hashing over word tokens. Needs no
  model, no network, no downloads, and is fully deterministic across processes
  (uses hashlib, not the salted built-in ``hash()``). Good enough for lexical
  semantic search and powers the offline test suite. This is the default.
* ``OllamaEmbedder`` — higher-quality dense embeddings from a local Ollama model
  (default ``nomic-embed-text``) via the OpenAI-compatible ``/v1/embeddings``
  endpoint. Opt in with ``AIOS_EMBEDDINGS=ollama``.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.error
import urllib.request

_TOKEN = re.compile(r"[a-z0-9]+")


class EmbeddingError(RuntimeError):
    """Raised when embeddings cannot be produced."""


def _tokens(text: str):
    return _TOKEN.findall(text.lower())


def _normalize(vec):
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


class Embedder:
    name = "base"
    dim = 0

    def embed(self, texts):  # pragma: no cover - interface
        raise NotImplementedError


class HashingEmbedder(Embedder):
    """Deterministic feature-hashing embedder. No model, no network."""

    name = "hashing"

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _hash(self, token: str):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        n = int.from_bytes(digest, "big")
        index = n % self.dim
        sign = 1.0 if (n // self.dim) % 2 == 0 else -1.0
        return index, sign

    def _embed_one(self, text: str):
        vec = [0.0] * self.dim
        for token in _tokens(text):
            index, sign = self._hash(token)
            vec[index] += sign
        return _normalize(vec)

    def embed(self, texts):
        return [self._embed_one(t) for t in texts]


class OllamaEmbedder(Embedder):
    name = "ollama"

    def __init__(self, base_url: str, model: str = "nomic-embed-text"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def embed(self, texts):
        payload = {"model": self.model, "input": list(texts)}
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.base_url + "/v1/embeddings",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                out = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            raise EmbeddingError(
                f"ollama embeddings HTTP {exc.code}: {body} "
                f"(try `ollama pull {self.model}`)"
            ) from exc
        except urllib.error.URLError as exc:
            raise EmbeddingError(
                f"cannot reach ollama at {self.base_url}: {exc.reason}. "
                "Start it with `ollama serve`."
            ) from exc
        try:
            return [_normalize(item["embedding"]) for item in out["data"]]
        except (KeyError, TypeError) as exc:
            raise EmbeddingError(f"unexpected embeddings response: {out!r}") from exc


def make_embedder(config) -> Embedder:
    if config.embeddings == "hashing":
        return HashingEmbedder()
    if config.embeddings == "ollama":
        return OllamaEmbedder(config.ollama_url, config.embed_model)
    raise EmbeddingError(
        f"unknown embeddings backend: {config.embeddings!r} (expected 'hashing' or 'ollama')"
    )
