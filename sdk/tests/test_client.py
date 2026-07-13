"""Integration tests: drive the SDK against a real aiosd (mock backend).

This proves the SDK works against the actual daemon and its frozen v1 contract —
not a mock of the API. The daemon package (`aiosd`) lives in ../ai-core; we add
it to the path only for the test harness (the SDK itself never imports it).
"""

import os
import sys
import tempfile
import threading
import unittest

_SDK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO = os.path.dirname(_SDK_DIR)
sys.path.insert(0, _SDK_DIR)                          # aios_sdk
sys.path.insert(0, os.path.join(_REPO, "ai-core"))   # aiosd (daemon, for the harness)

from aios_sdk import AIOSClient, APIError, ChatResult, Notification  # noqa: E402
from aiosd.config import Config  # noqa: E402
from aiosd.server import build_server  # noqa: E402


class TestSDK(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cfg = Config.from_env({"AIOS_BACKEND": "mock", "AIOS_PORT": "0",
                               "AIOS_DB_PATH": ":memory:", "AIOS_AUDIT": "off",
                               "AIOS_NOTIFY_DESKTOP": "off",
                               "AIOS_NOTIFICATIONS_PATH": os.path.join(cls.tmp.name, "n.json")})
        cls.httpd = build_server(cfg)
        port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.aios = AIOSClient(f"http://127.0.0.1:{port}")

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.httpd.aios_state.storage.close()
        cls.tmp.cleanup()

    def test_health_and_version(self):
        self.assertEqual(self.aios.health()["status"], "ok")
        self.assertEqual(self.aios.version()["api_version"], 1)

    def test_ask_returns_chat_result(self):
        r = self.aios.ask("ping")
        self.assertIsInstance(r, ChatResult)
        self.assertEqual(r.status, "complete")
        self.assertIn("ping", r.reply)
        self.assertFalse(r.needs_approval)

    def test_stream(self):
        text = "".join(self.aios.stream("stream me now"))
        self.assertIn("stream me now", text)

    def test_search_returns_typed_results(self):
        results = self.aios.search("anything")  # empty index -> empty list
        self.assertIsInstance(results, list)

    def test_tools(self):
        names = {t["name"] for t in self.aios.tools()}
        self.assertIn("read_file", names)

    def test_session_lifecycle(self):
        s = self.aios.create_session("work")
        self.assertTrue(s.id)
        self.aios.ask("remember this", session=s.id)
        detail = self.aios.session(s.id)
        self.assertEqual(len(detail["messages"]), 2)
        self.assertIn(s.id, [x.id for x in self.aios.sessions()])
        self.assertTrue(self.aios.delete_session(s.id))

    def test_grant_and_revoke(self):
        s = self.aios.create_session()
        self.assertIn("write_file", self.aios.grant(s.id, "write_file"))
        self.assertEqual(self.aios.revoke(s.id, "write_file"), [])

    def test_notifications(self):
        n = self.aios.notify("hello", body="world", level="success")
        self.assertIsInstance(n, Notification)
        items, unread = self.aios.notifications()
        self.assertGreaterEqual(unread, 1)
        self.assertTrue(any(x.title == "hello" for x in items))
        self.aios.mark_read()
        _, unread_after = self.aios.notifications()
        self.assertEqual(unread_after, 0)

    def test_api_error_on_bad_request(self):
        with self.assertRaises(APIError) as ctx:
            self.aios.ask("")  # missing prompt -> 400
        self.assertEqual(ctx.exception.status, 400)


class TestAuth(unittest.TestCase):
    def test_token_required(self):
        tmp = tempfile.TemporaryDirectory()
        cfg = Config.from_env({"AIOS_BACKEND": "mock", "AIOS_PORT": "0",
                               "AIOS_DB_PATH": ":memory:", "AIOS_TOKEN": "s3cret",
                               "AIOS_AUDIT": "off", "AIOS_NOTIFY_DESKTOP": "off",
                               "AIOS_NOTIFICATIONS_PATH": os.path.join(tmp.name, "n.json")})
        httpd = build_server(cfg)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(APIError) as ctx:
                AIOSClient(f"http://127.0.0.1:{port}").sessions()
            self.assertEqual(ctx.exception.status, 401)
            # with the token it works
            ok = AIOSClient(f"http://127.0.0.1:{port}", token="s3cret").sessions()
            self.assertIsInstance(ok, list)
        finally:
            httpd.shutdown()
            httpd.server_close()
            httpd.aios_state.storage.close()
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
