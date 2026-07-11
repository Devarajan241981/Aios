"""Retrieval: turn a query into relevant, cited excerpts from the vector store.

This is the RAG step that the Assistant injects before answering. Keeping it in
its own module means the same retriever backs both the ``/v1/search`` endpoint
and in-chat grounding.
"""

from __future__ import annotations


class Retriever:
    def __init__(self, store, embedder, top_k: int = 4, min_score: float = 0.0):
        self.store = store
        self.embedder = embedder
        self.top_k = top_k
        self.min_score = min_score

    def retrieve(self, query: str):
        if len(self.store) == 0:
            return []
        query_vec = self.embedder.embed([query])[0]
        hits = self.store.search(query_vec, self.top_k)
        return [h for h in hits if h["score"] > self.min_score]

    @staticmethod
    def render(hits) -> str:
        return "\n\n".join(f"[{h['source']}]\n{h['text']}" for h in hits)
