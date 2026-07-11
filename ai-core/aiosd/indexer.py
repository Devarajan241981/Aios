"""Filesystem indexer: walk paths, read text files, chunk, embed, store.

Deliberately conservative about what it reads — only known text extensions,
skips hidden and dependency directories, and caps file size — so pointing it at
a home directory does something sensible instead of trying to embed binaries.
"""

from __future__ import annotations

import os

TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".org",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".sh", ".rb", ".go", ".rs", ".c", ".h",
    ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg",
    ".html", ".css", ".csv", ".log", ".tex",
}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".mypy_cache"}
MAX_BYTES = 1_000_000  # skip files larger than ~1 MB


def iter_files(paths):
    for path in paths:
        if os.path.isfile(path):
            if _is_indexable(path):
                yield path
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
                for name in files:
                    full = os.path.join(root, name)
                    if _is_indexable(full):
                        yield full


def _is_indexable(path: str) -> bool:
    if os.path.splitext(path)[1].lower() not in TEXT_EXTENSIONS:
        return False
    try:
        return os.path.getsize(path) <= MAX_BYTES
    except OSError:
        return False


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def chunk_text(text: str, size: int = 1200, overlap: int = 200):
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks = []
    start = 0
    step = max(1, size - overlap)
    while start < len(text):
        chunks.append(text[start:start + size])
        start += step
    return chunks


def index_paths(paths, embedder, store) -> int:
    """Index the given files/dirs into ``store``. Returns number of chunks added."""
    texts = []
    meta = []  # (source, chunk_index)
    for path in iter_files(paths):
        content = read_text(path)
        for i, chunk in enumerate(chunk_text(content)):
            texts.append(chunk)
            meta.append((path, i))

    if not texts:
        return 0

    vectors = embedder.embed(texts)
    records = [
        {"id": f"{source}#{idx}", "source": source, "text": text, "vector": vector}
        for (source, idx), text, vector in zip(meta, texts, vectors)
    ]
    store.add(records)
    return len(records)
