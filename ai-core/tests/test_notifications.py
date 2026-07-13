import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from aiosd.config import Config
from aiosd.notifications import DesktopChannel, NotificationCenter, NotificationChannel
from aiosd.server import build_server


class TestNotificationCenter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "n.json")
        self.c = NotificationCenter(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_notify_and_list(self):
        self.c.notify("hello", "world", "info", "test")
        items = self.c.list()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "hello")
        self.assertFalse(items[0]["read"])

    def test_unread_and_mark(self):
        n = self.c.notify("a")
        self.c.notify("b")
        self.assertEqual(self.c.unread_count(), 2)
        self.assertTrue(self.c.mark_read(n["id"]))
        self.assertEqual(self.c.unread_count(), 1)
        self.assertEqual(self.c.mark_all_read(), 1)
        self.assertEqual(self.c.unread_count(), 0)

    def test_newest_first_and_unread_only(self):
        self.c.notify("first")
        second = self.c.notify("second")
        self.assertEqual(self.c.list()[0]["title"], "second")
        self.c.mark_read(second["id"])
        self.assertEqual([x["title"] for x in self.c.list(unread_only=True)], ["first"])

    def test_persistence(self):
        self.c.notify("persist")
        self.assertEqual(len(NotificationCenter(self.path).list()), 1)

    def test_clear(self):
        self.c.notify("x")
        self.assertEqual(self.c.clear(), 1)
        self.assertEqual(self.c.list(), [])

    def test_trim_to_max_keep(self):
        c = NotificationCenter(self.path, max_keep=3)
        for i in range(5):
            c.notify(str(i))
        titles = [n["title"] for n in c.list()]
        self.assertEqual(len(titles), 3)
        self.assertIn("4", titles)
        self.assertNotIn("0", titles)

    def test_invalid_level_defaults_to_info(self):
        self.assertEqual(self.c.notify("t", level="bogus")["level"], "info")


class TestDesktopChannel(unittest.TestCase):
    def test_is_channel_and_never_raises(self):
        ch = DesktopChannel()
        self.assertIsInstance(ch, NotificationChannel)
        ch.deliver({"title": "t", "body": "b", "level": "info"})  # no-op if no notify-send


class TestNotificationsAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cfg = Config.from_env({"AIOS_BACKEND": "mock", "AIOS_PORT": "0",
                               "AIOS_DB_PATH": ":memory:", "AIOS_NOTIFY_DESKTOP": "off",
                               "AIOS_NOTIFICATIONS_PATH": os.path.join(cls.tmp.name, "n.json")})
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

    def _call(self, method, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                     data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def test_create_list_read_clear(self):
        code, created = self._call("POST", "/v1/notifications",
                                   {"title": "build done", "level": "success"})
        self.assertEqual(code, 201)
        self.assertEqual(created["level"], "success")

        code, body = self._call("GET", "/v1/notifications")
        self.assertEqual(code, 200)
        self.assertGreaterEqual(body["unread"], 1)
        self.assertTrue(any(n["title"] == "build done" for n in body["notifications"]))

        code, r = self._call("POST", "/v1/notifications/read", {})
        self.assertEqual(code, 200)
        self.assertGreaterEqual(r["read_all"], 1)

        _, body = self._call("GET", "/v1/notifications")
        self.assertEqual(body["unread"], 0)

        code, c = self._call("DELETE", "/v1/notifications")
        self.assertEqual(code, 200)
        self.assertGreaterEqual(c["cleared"], 1)

    def test_missing_title_is_400(self):
        code, _ = self._call("POST", "/v1/notifications", {})
        self.assertEqual(code, 400)


if __name__ == "__main__":
    unittest.main()
