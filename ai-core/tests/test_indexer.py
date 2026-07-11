import os
import tempfile
import unittest

from aiosd.embeddings import HashingEmbedder
from aiosd.indexer import chunk_text, index_paths, iter_files
from aiosd.store import VectorStore


class TestChunking(unittest.TestCase):
    def test_short_text_single_chunk(self):
        self.assertEqual(chunk_text("hello"), ["hello"])

    def test_empty_text_no_chunks(self):
        self.assertEqual(chunk_text("   "), [])

    def test_long_text_overlapping_chunks(self):
        text = "x" * 3000
        chunks = chunk_text(text, size=1200, overlap=200)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 1200 for c in chunks))


class TestIndexing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = self.tmp.name
        with open(os.path.join(base, "budget.md"), "w") as fh:
            fh.write("# Budget\nThe marketing budget for Q3 is fifty thousand dollars.")
        with open(os.path.join(base, "cats.txt"), "w") as fh:
            fh.write("My cat likes to sleep in the afternoon sun.")
        # a binary-ish file that must be skipped
        with open(os.path.join(base, "image.png"), "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n not really text")

    def tearDown(self):
        self.tmp.cleanup()

    def test_iter_files_skips_non_text(self):
        files = list(iter_files([self.tmp.name]))
        names = {os.path.basename(f) for f in files}
        self.assertEqual(names, {"budget.md", "cats.txt"})

    def test_index_and_search(self):
        store = VectorStore()
        embedder = HashingEmbedder()
        count = index_paths([self.tmp.name], embedder, store)
        self.assertGreaterEqual(count, 2)

        q = embedder.embed(["how much is the marketing budget"])[0]
        top = store.search(q, k=1)[0]
        self.assertTrue(top["source"].endswith("budget.md"))

    def test_reindex_is_idempotent(self):
        store = VectorStore()
        embedder = HashingEmbedder()
        index_paths([self.tmp.name], embedder, store)
        n1 = len(store)
        index_paths([self.tmp.name], embedder, store)  # same files again
        self.assertEqual(len(store), n1)


if __name__ == "__main__":
    unittest.main()
