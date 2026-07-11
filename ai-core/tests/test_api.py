import json
import threading
import unittest
import urllib.error
import urllib.request

from aiosd.config import Config
from aiosd.server import build_server


def _serve(env):
    cfg = Config.from_env({**{"AIOS_BACKEND": "mock", "AIOS_PORT": "0",
                              "AIOS_DB_PATH": ":memory:"}, **env})
    httpd = build_server(cfg)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, port


class _Client:
    def __init__(self, port, token=None):
        self.port = port
        self.token = token

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def call(self, method, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                     data=data, method=method, headers=self._headers())
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            return exc.code, (json.loads(body) if body else {})


class TestSessionsAndTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd, port = _serve({})
        cls.c = _Client(port)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.httpd.aios_state.storage.close()

    def test_version(self):
        code, body = self.c.call("GET", "/version")
        self.assertEqual(code, 200)
        self.assertIn("version", body)

    def test_tools_listed(self):
        code, body = self.c.call("GET", "/v1/tools")
        self.assertEqual(code, 200)
        self.assertTrue(body["enabled"])
        names = {t["name"] for t in body["tools"]}
        self.assertIn("read_file", names)
        self.assertIn("search_notes", names)

    def test_session_lifecycle_and_persistence(self):
        # create
        code, sess = self.c.call("POST", "/v1/sessions", {"title": "temp"})
        self.assertEqual(code, 201)
        sid = sess["id"]

        # chat within the session persists user + assistant turns
        code, body = self.c.call("POST", "/v1/chat",
                                 {"prompt": "remember the alamo", "session_id": sid})
        self.assertEqual(code, 200)
        self.assertEqual(body["session_id"], sid)

        # transcript has both turns; title auto-set from first prompt
        code, got = self.c.call("GET", f"/v1/sessions/{sid}")
        self.assertEqual(code, 200)
        self.assertEqual(len(got["messages"]), 2)
        self.assertEqual(got["session"]["title"], "remember the alamo")

        # second turn accumulates
        self.c.call("POST", "/v1/chat", {"prompt": "and again", "session_id": sid})
        _, got2 = self.c.call("GET", f"/v1/sessions/{sid}")
        self.assertEqual(len(got2["messages"]), 4)

        # listing shows it, deletion works
        _, listing = self.c.call("GET", "/v1/sessions")
        self.assertIn(sid, [s["id"] for s in listing["sessions"]])
        code, deleted = self.c.call("DELETE", f"/v1/sessions/{sid}")
        self.assertTrue(deleted["deleted"])
        code, _ = self.c.call("GET", f"/v1/sessions/{sid}")
        self.assertEqual(code, 404)

    def test_chat_with_tools_returns_steps(self):
        # mock backend uses no tools, so steps is empty but the shape is present
        code, body = self.c.call("POST", "/v1/chat", {"prompt": "hi", "use_tools": True})
        self.assertEqual(code, 200)
        self.assertIn("steps", body)


class TestAuthAndLimits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd, port = _serve({"AIOS_TOKEN": "s3cret", "AIOS_MAX_BODY_BYTES": "50"})
        cls.port = port

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.httpd.aios_state.storage.close()

    def test_health_is_open(self):
        code, _ = _Client(self.port).call("GET", "/health")
        self.assertEqual(code, 200)

    def test_unauthorized_without_token(self):
        code, _ = _Client(self.port).call("GET", "/v1/sessions")
        self.assertEqual(code, 401)

    def test_authorized_with_token(self):
        code, _ = _Client(self.port, token="s3cret").call("GET", "/v1/sessions")
        self.assertEqual(code, 200)

    def test_body_too_large(self):
        big = {"prompt": "x" * 500}
        code, _ = _Client(self.port, token="s3cret").call("POST", "/v1/chat", big)
        self.assertEqual(code, 413)


if __name__ == "__main__":
    unittest.main()
