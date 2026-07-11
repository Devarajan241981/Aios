import os
import tempfile
import unittest

from aiosd.config import Config
from aiosd.embeddings import HashingEmbedder
from aiosd.retriever import Retriever
from aiosd.store import VectorStore
from aiosd.tools import Registry, Tool, ToolContext, default_registry


class TestSafeTools(unittest.TestCase):
    def setUp(self):
        self.reg = default_registry()

    def test_current_time(self):
        ctx = ToolContext(config=Config.from_env({}))
        res = self.reg.execute("current_time", {}, ctx)
        self.assertTrue(res["ok"])
        self.assertRegex(res["result"], r"\d{4}-\d{2}-\d{2}T")

    def test_system_info(self):
        ctx = ToolContext(config=Config.from_env({}),
                          context_provider=lambda: {"os": "TestOS", "host": "h"})
        res = self.reg.execute("system_info", {}, ctx)
        self.assertIn("os: TestOS", res["result"])

    def test_unknown_tool(self):
        ctx = ToolContext(config=Config.from_env({}))
        res = self.reg.execute("nope", {}, ctx)
        self.assertFalse(res["ok"])
        self.assertIn("unknown tool", res["error"])


class TestFilesystemSandbox(unittest.TestCase):
    def setUp(self):
        self.reg = default_registry()
        self.tmp = tempfile.TemporaryDirectory()
        self.file = os.path.join(self.tmp.name, "note.txt")
        with open(self.file, "w") as fh:
            fh.write("secret sauce")
        # allow the temp dir explicitly
        self.ctx = ToolContext(config=Config.from_env({"AIOS_ALLOWED_ROOTS": self.tmp.name}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_file_within_root(self):
        res = self.reg.execute("read_file", {"path": self.file}, self.ctx)
        self.assertTrue(res["ok"])
        self.assertIn("secret sauce", res["result"])

    def test_read_file_outside_root_denied(self):
        ctx = ToolContext(config=Config.from_env({}))  # only home allowed
        res = self.reg.execute("read_file", {"path": "/etc/hosts"}, ctx)
        self.assertFalse(res["ok"])
        self.assertIn("not allowed", res["error"])

    def test_list_dir(self):
        res = self.reg.execute("list_dir", {"path": self.tmp.name}, self.ctx)
        self.assertTrue(res["ok"])
        self.assertIn("note.txt", res["result"])

    def test_read_missing_file(self):
        res = self.reg.execute("read_file", {"path": os.path.join(self.tmp.name, "no.txt")},
                               self.ctx)
        self.assertFalse(res["ok"])


class TestSearchNotesTool(unittest.TestCase):
    def test_requires_retriever(self):
        reg = default_registry()
        res = reg.execute("search_notes", {"query": "x"}, ToolContext(config=Config.from_env({})))
        self.assertFalse(res["ok"])

    def test_returns_matches(self):
        store = VectorStore()
        emb = HashingEmbedder()
        text = "The quarterly revenue target is one million."
        store.add([{"id": "a#0", "source": "/f.md", "text": text,
                    "vector": emb.embed([text])[0]}])
        ctx = ToolContext(config=Config.from_env({}),
                          retriever=Retriever(store, emb, top_k=1))
        res = default_registry().execute("search_notes", {"query": "revenue target"}, ctx)
        self.assertTrue(res["ok"])
        self.assertIn("/f.md", res["result"])


class TestApprovalGate(unittest.TestCase):
    def _registry_with_mutating(self):
        reg = Registry()
        reg.register(Tool("delete_all", "danger", {"type": "object", "properties": {}},
                          lambda a, c: "boom", safe=False))
        return reg

    def test_mutating_blocked_without_approval(self):
        reg = self._registry_with_mutating()
        res = reg.execute("delete_all", {}, ToolContext(config=Config.from_env({})))
        self.assertFalse(res["ok"])
        self.assertTrue(res["needs_approval"])

    def test_mutating_runs_with_approval(self):
        reg = self._registry_with_mutating()
        res = reg.execute("delete_all", {}, ToolContext(config=Config.from_env({})), approve=True)
        self.assertTrue(res["ok"])
        self.assertEqual(res["result"], "boom")


if __name__ == "__main__":
    unittest.main()
