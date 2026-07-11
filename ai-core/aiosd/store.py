"""A tiny local vector store.

In-memory records keyed by id, cosine-similarity search (vectors are stored
already L2-normalized, so cosine is a dot product), and JSON persistence to a
local file. No server, no external dependency. Fine for tens of thousands of
chunks on a laptop; a real ANN index can slot in behind the same interface
later.

A record is: {"id": str, "source": str, "text": str, "vector": list[float]}.
"""

from __future__ import annotations

import json
import os


def _dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


class VectorStore:
    def __init__(self):
        self._by_id: dict[str, dict] = {}

    def __len__(self) -> int:
        return len(self._by_id)

    def add(self, records) -> None:
        for rec in records:
            self._by_id[rec["id"]] = rec

    def clear(self) -> None:
        self._by_id.clear()

    def sources(self):
        return sorted({r["source"] for r in self._by_id.values()})

    def search(self, query_vec, k: int = 4):
        scored = (
            (_dot(query_vec, rec["vector"]), rec) for rec in self._by_id.values()
        )
        top = sorted(scored, key=lambda pair: pair[0], reverse=True)[:k]
        return [
            {"source": rec["source"], "text": rec["text"], "score": round(score, 4)}
            for score, rec in top
        ]

    def save(self, path: str) -> None:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(list(self._by_id.values()), fh)
        os.replace(tmp, path)  # atomic

    def load(self, path: str) -> None:
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as fh:
            records = json.load(fh)
        self.add(records)
