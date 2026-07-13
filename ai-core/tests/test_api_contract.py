"""Platform API v1 contract tests.

These pin the response shapes documented in
docs/architecture/04-platform-api-v1.md. If a field is renamed, removed, or
retyped, these fail — that is the enforcement mechanism for the v1 freeze.
Add to these when the API grows (additively); never loosen them to make a
breaking change pass.
"""

import json
import threading
import unittest
import urllib.error
import urllib.request

from aiosd import API_VERSION
from aiosd.config import Config
from aiosd.server import build_server


def _serve(env):
    cfg = Config.from_env({**{"AIOS_BACKEND": "mock", "AIOS_PORT": "0",
                              "AIOS_DB_PATH": ":memory:", "AIOS_AUDIT": "off"}, **env})
    httpd = build_server(cfg)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, httpd.server_address[1]


class _Client:
    def __init__(self, port, token=None):
        self.port, self.token = port, token

    def call(self, method, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                     data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            return exc.code, (json.loads(body) if body else {})


def _has(testcase, obj, keys):
    for k in keys:
        testcase.assertIn(k, obj)


class TestContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd, port = _serve({})
        cls.c = _Client(port)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.httpd.aios_state.storage.close()

    # -- operations plane --------------------------------------------------
    def test_health(self):
        code, b = self.c.call("GET", "/health")
        self.assertEqual(code, 200)
        _has(self, b, ["status", "service", "version", "api_version", "backend", "index", "tools"])
        self.assertEqual(b["api_version"], API_VERSION)
        _has(self, b["index"], ["documents", "embeddings"])

    def test_version(self):
        code, b = self.c.call("GET", "/version")
        self.assertEqual(code, 200)
        _has(self, b, ["version", "api_version", "python"])

    # -- application data plane -------------------------------------------
    def test_chat_complete_shape(self):
        code, b = self.c.call("POST", "/v1/chat", {"prompt": "hi"})
        self.assertEqual(code, 200)
        _has(self, b, ["reply", "model", "status"])
        self.assertEqual(b["status"], "complete")

    def test_chat_missing_prompt_is_400_error_shape(self):
        code, b = self.c.call("POST", "/v1/chat", {})
        self.assertEqual(code, 400)
        self.assertIn("error", b)

    def test_tools_shape(self):
        code, b = self.c.call("GET", "/v1/tools")
        self.assertEqual(code, 200)
        _has(self, b, ["enabled", "tools"])
        for t in b["tools"]:
            _has(self, t, ["name", "description", "safe"])

    def test_search_shape(self):
        code, b = self.c.call("POST", "/v1/search", {"query": "x"})
        self.assertEqual(code, 200)
        self.assertIsInstance(b["results"], list)

    def test_index_stats_shape(self):
        code, b = self.c.call("GET", "/v1/index/stats")
        self.assertEqual(code, 200)
        _has(self, b, ["documents", "sources"])

    def test_sessions_lifecycle_shapes(self):
        code, created = self.c.call("POST", "/v1/sessions", {"title": "t"})
        self.assertEqual(code, 201)
        _has(self, created, ["id", "title", "created_at", "updated_at", "messages"])
        sid = created["id"]

        code, got = self.c.call("GET", f"/v1/sessions/{sid}")
        self.assertEqual(code, 200)
        _has(self, got, ["session", "messages", "grants"])

        code, listing = self.c.call("GET", "/v1/sessions")
        self.assertEqual(code, 200)
        self.assertIsInstance(listing["sessions"], list)

        code, grants = self.c.call("POST", f"/v1/sessions/{sid}/grants", {"tool": "write_file"})
        self.assertEqual(code, 200)
        self.assertIn("write_file", grants["grants"])

        code, deleted = self.c.call("DELETE", f"/v1/sessions/{sid}")
        self.assertEqual(code, 200)
        self.assertIn("deleted", deleted)

    def test_unknown_session_is_404_error_shape(self):
        code, b = self.c.call("GET", "/v1/sessions/nope")
        self.assertEqual(code, 404)
        self.assertIn("error", b)

    def test_audit_shape(self):
        code, b = self.c.call("GET", "/v1/audit")
        self.assertEqual(code, 200)
        self.assertIsInstance(b["events"], list)

    def test_notifications_shape(self):
        code, b = self.c.call("GET", "/v1/notifications")
        self.assertEqual(code, 200)
        self.assertIsInstance(b["notifications"], list)
        self.assertIn("unread", b)


class TestContractAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd, cls.port = _serve({"AIOS_TOKEN": "s3cret"})

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.httpd.aios_state.storage.close()

    def test_health_is_public(self):
        self.assertEqual(_Client(self.port).call("GET", "/health")[0], 200)

    def test_data_plane_requires_token(self):
        self.assertEqual(_Client(self.port).call("GET", "/v1/sessions")[0], 401)
        self.assertEqual(
            _Client(self.port, token="s3cret").call("GET", "/v1/sessions")[0], 200)


if __name__ == "__main__":
    unittest.main()
