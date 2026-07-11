import math
import unittest

from aiosd.embeddings import EmbeddingError, HashingEmbedder, make_embedder
from aiosd.config import Config


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b))


class TestHashingEmbedder(unittest.TestCase):
    def setUp(self):
        self.e = HashingEmbedder(dim=256)

    def test_deterministic_across_instances(self):
        v1 = HashingEmbedder(dim=256).embed(["the quick brown fox"])[0]
        v2 = HashingEmbedder(dim=256).embed(["the quick brown fox"])[0]
        self.assertEqual(v1, v2)

    def test_vectors_are_normalized(self):
        v = self.e.embed(["hello world of embeddings"])[0]
        self.assertAlmostEqual(math.sqrt(sum(x * x for x in v)), 1.0, places=6)

    def test_similar_text_is_closer_than_unrelated(self):
        base = self.e.embed(["budget planning for the marketing project"])[0]
        near = self.e.embed(["marketing project budget plan"])[0]
        far = self.e.embed(["a photo of a cat sleeping"])[0]
        self.assertGreater(_cos(base, near), _cos(base, far))

    def test_empty_text_is_safe(self):
        v = self.e.embed([""])[0]
        self.assertEqual(len(v), 256)


class TestFactory(unittest.TestCase):
    def test_default_is_hashing(self):
        e = make_embedder(Config.from_env({}))
        self.assertIsInstance(e, HashingEmbedder)

    def test_unknown_raises(self):
        with self.assertRaises(EmbeddingError):
            make_embedder(Config.from_env({"AIOS_EMBEDDINGS": "nope"}))


if __name__ == "__main__":
    unittest.main()
