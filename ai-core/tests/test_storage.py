import unittest

from aiosd.config import Config
from aiosd.storage import SessionStore, SqliteStore, open_store


class TestSeam(unittest.TestCase):
    def test_sqlite_is_a_session_store(self):
        store = SqliteStore(":memory:")
        self.assertIsInstance(store, SessionStore)
        store.close()

    def test_open_store_returns_session_store(self):
        store = open_store(Config.from_env({"AIOS_DB_PATH": ":memory:"}))
        self.assertIsInstance(store, SessionStore)
        store.close()


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.s = SqliteStore(":memory:")

    def tearDown(self):
        self.s.close()

    def test_create_and_get(self):
        sid = self.s.create_session(title="Hello")
        sess = self.s.get_session(sid)
        self.assertEqual(sess["title"], "Hello")
        self.assertEqual(sess["messages"], 0)

    def test_add_and_get_messages(self):
        sid = self.s.create_session()
        self.s.add_message(sid, "user", "hi")
        self.s.add_message(sid, "assistant", "hello")
        msgs = self.s.get_messages(sid)
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant"])
        self.assertEqual(msgs[1]["content"], "hello")

    def test_add_message_autocreates_session(self):
        self.s.add_message("adhoc", "user", "hey")
        self.assertEqual(len(self.s.get_messages("adhoc")), 1)

    def test_history_limit(self):
        sid = self.s.create_session()
        for i in range(10):
            self.s.add_message(sid, "user", str(i))
        last3 = self.s.get_messages(sid, limit=3)
        self.assertEqual([m["content"] for m in last3], ["7", "8", "9"])

    def test_rename(self):
        sid = self.s.create_session()
        self.s.rename_session(sid, "Renamed")
        self.assertEqual(self.s.get_session(sid)["title"], "Renamed")

    def test_delete_cascades(self):
        sid = self.s.create_session()
        self.s.add_message(sid, "user", "x")
        self.assertTrue(self.s.delete_session(sid))
        self.assertIsNone(self.s.get_session(sid))
        self.assertEqual(self.s.get_messages(sid), [])  # cascade removed messages

    def test_grants(self):
        sid = self.s.create_session()
        self.s.grant_tool(sid, "write_file")
        self.s.grant_tool(sid, "write_file")  # idempotent
        self.s.grant_tool(sid, "move_file")
        self.assertEqual(self.s.list_grants(sid), ["move_file", "write_file"])
        self.assertTrue(self.s.revoke_tool(sid, "move_file"))
        self.assertEqual(self.s.list_grants(sid), ["write_file"])
        self.assertFalse(self.s.revoke_tool(sid, "nope"))

    def test_grants_cascade_on_delete(self):
        sid = self.s.create_session()
        self.s.grant_tool(sid, "write_file")
        self.s.delete_session(sid)
        self.assertEqual(self.s.list_grants(sid), [])

    def test_list_orders_by_recency(self):
        a = self.s.create_session(title="A")
        b = self.s.create_session(title="B")
        self.s.add_message(a, "user", "later")  # bumps A's updated_at
        ids = [s["id"] for s in self.s.list_sessions()]
        self.assertEqual(ids[0], a)
        self.assertIn(b, ids)


if __name__ == "__main__":
    unittest.main()
