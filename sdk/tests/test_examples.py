"""Run the example apps against a real aiosd — dogfooding the SDK on genuine
consumers, and keeping the examples from bit-rotting."""

import os
import sys
import tempfile
import threading
import unittest

_SDK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO = os.path.dirname(_SDK_DIR)
sys.path.insert(0, _SDK_DIR)                          # aios_sdk
sys.path.insert(0, os.path.join(_REPO, "ai-core"))   # aiosd (harness only)
sys.path.insert(0, os.path.join(_REPO, "examples"))  # the example modules

import briefing  # noqa: E402
import notes_qa  # noqa: E402
from aios_sdk import AIOSClient  # noqa: E402
from aiosd.config import Config  # noqa: E402
from aiosd.server import build_server  # noqa: E402


class TestExamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cfg = Config.from_env({"AIOS_BACKEND": "mock", "AIOS_PORT": "0",
                               "AIOS_DB_PATH": ":memory:", "AIOS_AUDIT": "off",
                               "AIOS_NOTIFY_DESKTOP": "off",
                               "AIOS_NOTIFICATIONS_PATH": os.path.join(cls.tmp.name, "n.json"),
                               "AIOS_INDEX_PATH": os.path.join(cls.tmp.name, "index.json")})
        cls.httpd = build_server(cfg)
        port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.aios = AIOSClient(f"http://127.0.0.1:{port}")

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.httpd.aios_state.storage.close()
        cls.tmp.cleanup()

    def test_briefing_asks_and_notifies(self):
        reply = briefing.run(self.aios, "status please")
        self.assertIn("status please", reply)
        items, unread = self.aios.notifications()
        self.assertGreaterEqual(unread, 1)
        self.assertTrue(any(n.title == "Briefing" for n in items))

    def test_notes_qa_indexes_and_answers(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "note.md"), "w") as fh:
                fh.write("The launch is scheduled for September.")
            reply = notes_qa.run(self.aios, d, "when is the launch?")
            self.assertIn("when is the launch?", reply)  # mock echoes the prompt
            self.assertGreaterEqual(self.aios.index_stats()["documents"], 1)


if __name__ == "__main__":
    unittest.main()
