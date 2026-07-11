import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from aiosd.assistant import Assistant
from aiosd.backends import MockBackend
from aiosd.config import Config
from aiosd.embeddings import HashingEmbedder
from aiosd.retriever import Retriever
from aiosd.server import build_server
from aiosd.store import VectorStore


class TestAssistantRetrieval(unittest.TestCase):
    def _assistant_with_docs(self):
        store = VectorStore()
        embedder = HashingEmbedder()
        store.add([
            {"id": "budget#0", "source": "/notes/budget.md",
             "text": "The marketing budget for Q3 is fifty thousand dollars.",
             "vector": embedder.embed(["The marketing budget for Q3 is fifty thousand dollars."])[0]},
            {"id": "cat#0", "source": "/notes/cats.txt",
             "text": "My cat sleeps in the afternoon.",
             "vector": embedder.embed(["My cat sleeps in the afternoon."])[0]},
        ])
        retriever = Retriever(store, embedder, top_k=1)
        cfg = Config.from_env({"AIOS_BACKEND": "mock"})
        return Assistant(MockBackend(), cfg, context_provider=lambda: {"host": "H"},
                         retriever=retriever)

    def test_relevant_excerpt_is_injected(self):
        a = self._assistant_with_docs()
        messages = a.build_messages("how much is the marketing budget?")
        joined = " ".join(m["content"] for m in messages if m["role"] == "system")
        self.assertIn("budget.md", joined)
        self.assertIn("fifty thousand", joined)

    def test_no_retriever_means_no_injection(self):
        cfg = Config.from_env({"AIOS_BACKEND": "mock"})
        a = Assistant(MockBackend(), cfg, context_provider=lambda: {"host": "H"})
        messages = a.build_messages("hi")
        self.assertEqual(len(messages), 2)  # system + user only


class TestServerRag(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        docs = os.path.join(cls.tmp.name, "docs")
        os.makedirs(docs)
        with open(os.path.join(docs, "budget.md"), "w") as fh:
            fh.write("The marketing budget for Q3 is fifty thousand dollars.")
        cls.docs = docs
        cls.index_path = os.path.join(cls.tmp.name, "index.json")

        cfg = Config.from_env({
            "AIOS_BACKEND": "mock",
            "AIOS_EMBEDDINGS": "hashing",
            "AIOS_PORT": "0",
            "AIOS_INDEX_PATH": cls.index_path,
            "AIOS_DB_PATH": ":memory:",
        })
        cls.httpd = build_server(cfg)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.httpd.aios_state.storage.close()
        cls.tmp.cleanup()

    def _post(self, path, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as resp:
            return resp.status, json.loads(resp.read().decode())

    def test_01_index(self):
        code, body = self._post("/v1/index", {"paths": [self.docs]})
        self.assertEqual(code, 200)
        self.assertGreaterEqual(body["indexed"], 1)
        self.assertTrue(os.path.exists(self.index_path))  # persisted

    def test_02_stats(self):
        code, body = self._get("/v1/index/stats")
        self.assertEqual(code, 200)
        self.assertGreaterEqual(body["documents"], 1)

    def test_03_search_finds_budget(self):
        code, body = self._post("/v1/search", {"query": "marketing budget", "k": 1})
        self.assertEqual(code, 200)
        self.assertTrue(body["results"])
        self.assertTrue(body["results"][0]["source"].endswith("budget.md"))

    def test_04_index_bad_paths(self):
        code, _ = self._post("/v1/index", {"paths": "notalist"})
        self.assertEqual(code, 400)

    def test_05_search_missing_query(self):
        code, _ = self._post("/v1/search", {})
        self.assertEqual(code, 400)


if __name__ == "__main__":
    unittest.main()
