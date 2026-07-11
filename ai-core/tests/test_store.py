import os
import tempfile
import unittest

from aiosd.store import VectorStore


def rec(id_, source, vector, text="t"):
    return {"id": id_, "source": source, "text": text, "vector": vector}


class TestVectorStore(unittest.TestCase):
    def test_add_and_len(self):
        s = VectorStore()
        s.add([rec("a", "f1", [1.0, 0.0]), rec("b", "f2", [0.0, 1.0])])
        self.assertEqual(len(s), 2)

    def test_dedup_by_id(self):
        s = VectorStore()
        s.add([rec("a", "f1", [1.0, 0.0], text="old")])
        s.add([rec("a", "f1", [1.0, 0.0], text="new")])
        self.assertEqual(len(s), 1)

    def test_search_ranks_by_cosine(self):
        s = VectorStore()
        s.add([
            rec("a", "f1", [1.0, 0.0], text="east"),
            rec("b", "f2", [0.0, 1.0], text="north"),
        ])
        hits = s.search([1.0, 0.0], k=2)
        self.assertEqual(hits[0]["text"], "east")
        self.assertGreaterEqual(hits[0]["score"], hits[1]["score"])

    def test_save_load_roundtrip(self):
        s = VectorStore()
        s.add([rec("a", "f1", [1.0, 0.0], text="hello")])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "index.json")
            s.save(path)  # also creates the directory
            self.assertTrue(os.path.exists(path))
            s2 = VectorStore()
            s2.load(path)
            self.assertEqual(len(s2), 1)
            self.assertEqual(s2.search([1.0, 0.0], 1)[0]["text"], "hello")

    def test_load_missing_is_noop(self):
        s = VectorStore()
        s.load("/nonexistent/path/index.json")
        self.assertEqual(len(s), 0)


if __name__ == "__main__":
    unittest.main()
