import json
import threading
import unittest
import urllib.error
import urllib.request

from aiosd.config import Config
from aiosd.server import build_server


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # port 0 -> OS assigns a free ephemeral port; mock backend -> no network
        cfg = Config.from_env({"AIOS_BACKEND": "mock", "AIOS_PORT": "0",
                               "AIOS_DB_PATH": ":memory:"})
        cls.httpd = build_server(cfg)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.httpd.aios_state.storage.close()

    def _get(self, path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def _post(self, path, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def test_health_ok(self):
        code, body = self._get("/health")
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["backend"]["ok"])

    def test_chat_roundtrip(self):
        code, body = self._post("/v1/chat", {"prompt": "ping"})
        self.assertEqual(code, 200)
        self.assertIn("ping", body["reply"])

    def test_chat_missing_prompt(self):
        code, body = self._post("/v1/chat", {})
        self.assertEqual(code, 400)
        self.assertIn("error", body)

    def test_unknown_route(self):
        code, _ = self._get("/nope")
        self.assertEqual(code, 404)


if __name__ == "__main__":
    unittest.main()
