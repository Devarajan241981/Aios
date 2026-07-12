import http.client
import json
import os
import socket
import stat
import tempfile
import threading
import unittest

from aiosd.config import Config
from aiosd.server import build_server
from aiosd.transport import (
    TcpHttpTransport,
    Transport,
    UnixHttpTransport,
    make_transport,
)


class TestFactory(unittest.TestCase):
    def test_default_is_tcp(self):
        t = make_transport(Config.from_env({}))
        self.assertIsInstance(t, TcpHttpTransport)
        self.assertEqual(t.name, "tcp")

    def test_unix_selected(self):
        t = make_transport(Config.from_env({"AIOS_TRANSPORT": "unix",
                                            "AIOS_SOCKET_PATH": "/tmp/x.sock"}))
        self.assertIsInstance(t, UnixHttpTransport)
        self.assertTrue(t.describe().startswith("http+unix://"))

    def test_are_transports(self):
        self.assertIsInstance(TcpHttpTransport("127.0.0.1", 0), Transport)
        self.assertIsInstance(UnixHttpTransport("/tmp/x.sock"), Transport)


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost")
        self._path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self._path)


class TestUnixTransportEndToEnd(unittest.TestCase):
    """The frozen v1 contract must work identically over a Unix socket."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.sock = os.path.join(cls.tmp.name, "aiosd.sock")
        cfg = Config.from_env({"AIOS_BACKEND": "mock", "AIOS_TRANSPORT": "unix",
                               "AIOS_SOCKET_PATH": cls.sock, "AIOS_DB_PATH": ":memory:",
                               "AIOS_AUDIT": "off"})
        cls.httpd = build_server(cfg)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.httpd.aios_state.storage.close()
        cls.tmp.cleanup()

    def _request(self, method, path, body=None):
        conn = _UnixConnection(self.sock)
        headers = {"Content-Type": "application/json"}
        conn.request(method, path, body=json.dumps(body) if body else None, headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        conn.close()
        return resp.status, data

    def test_socket_exists_and_is_owner_only(self):
        self.assertTrue(os.path.exists(self.sock))
        mode = stat.S_IMODE(os.stat(self.sock).st_mode)
        self.assertEqual(mode, 0o600)  # only the owner may talk to the daemon

    def test_health_over_unix_socket(self):
        code, body = self._request("GET", "/health")
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["api_version"], 1)

    def test_chat_over_unix_socket(self):
        code, body = self._request("POST", "/v1/chat", {"prompt": "ping"})
        self.assertEqual(code, 200)
        self.assertIn("ping", body["reply"])


class TestOverlongSocketPath(unittest.TestCase):
    def test_clear_error_not_traceback(self):
        cfg = Config.from_env({"AIOS_BACKEND": "mock", "AIOS_TRANSPORT": "unix",
                               "AIOS_SOCKET_PATH": "/tmp/" + ("x" * 120) + ".sock",
                               "AIOS_DB_PATH": ":memory:", "AIOS_AUDIT": "off"})
        with self.assertRaises(ValueError) as ctx:
            build_server(cfg)
        self.assertIn("too long", str(ctx.exception))


class TestSocketRemovedOnClose(unittest.TestCase):
    def test_close_unlinks_socket(self):
        with tempfile.TemporaryDirectory() as d:
            sock = os.path.join(d, "s.sock")
            cfg = Config.from_env({"AIOS_BACKEND": "mock", "AIOS_TRANSPORT": "unix",
                                   "AIOS_SOCKET_PATH": sock, "AIOS_DB_PATH": ":memory:",
                                   "AIOS_AUDIT": "off"})
            httpd = build_server(cfg)
            self.assertTrue(os.path.exists(sock))
            httpd.server_close()
            httpd.aios_state.storage.close()
            self.assertFalse(os.path.exists(sock))


if __name__ == "__main__":
    unittest.main()
