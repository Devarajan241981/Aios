import threading
import unittest
import urllib.error
import urllib.request

from aiosd.config import Config
from aiosd.server import build_server
from aiosd.ui import index_html


class TestUiTemplate(unittest.TestCase):
    def test_version_injected(self):
        html = index_html("9.9.9")
        self.assertIn("9.9.9", html)
        self.assertNotIn("__AIOS_VERSION__", html)

    def test_self_contained(self):
        html = index_html("1.0.0")
        # no external resources -> CSP-friendly / offline
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("src=", html)
        self.assertIn("<style>", html)  # CSS inlined

    def test_has_diff_preview_styling(self):
        html = index_html("1.0.0")
        self.assertIn("formatPreview", html)   # colored diff renderer
        self.assertIn("d-add", html)
        self.assertIn("d-del", html)


class TestUiServed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # token set to prove the UI is still reachable without auth
        cfg = Config.from_env({"AIOS_BACKEND": "mock", "AIOS_PORT": "0",
                               "AIOS_DB_PATH": ":memory:", "AIOS_TOKEN": "secret"})
        cls.httpd = build_server(cfg)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.httpd.aios_state.storage.close()

    def test_root_serves_html_without_auth(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/") as resp:
            self.assertEqual(resp.status, 200)
            self.assertTrue(resp.headers.get("Content-Type", "").startswith("text/html"))
            body = resp.read().decode()
        self.assertIn("AIOS", body)
        self.assertIn("<textarea", body)

    def test_api_still_protected(self):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/v1/sessions")
            self.fail("expected 401")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 401)


if __name__ == "__main__":
    unittest.main()
