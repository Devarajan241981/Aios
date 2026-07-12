import os
import tempfile
import unittest

from aiosd.audit import AuditLog, summarize_args


class TestAuditLog(unittest.TestCase):
    def test_record_and_tail(self):
        with tempfile.TemporaryDirectory() as d:
            log = AuditLog(os.path.join(d, "sub", "audit.log"))  # dir auto-created
            log.record({"event": "tool", "tool": "read_file", "ok": True})
            log.record({"event": "tool", "tool": "write_file", "ok": True})
            events = log.tail()
            self.assertEqual(len(events), 2)
            self.assertEqual(events[-1]["tool"], "write_file")
            self.assertIn("ts", events[0])

    def test_tail_limit(self):
        with tempfile.TemporaryDirectory() as d:
            log = AuditLog(os.path.join(d, "a.log"))
            for i in range(10):
                log.record({"event": "tool", "tool": str(i)})
            self.assertEqual([e["tool"] for e in log.tail(3)], ["7", "8", "9"])

    def test_disabled_is_noop(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.log")
            log = AuditLog(path, enabled=False)
            log.record({"event": "tool"})
            self.assertFalse(os.path.exists(path))
            self.assertEqual(log.tail(), [])

    def test_missing_file_tail_is_empty(self):
        self.assertEqual(AuditLog("/no/such/audit.log").tail(), [])


class TestSummarizeArgs(unittest.TestCase):
    def test_truncates_long_strings(self):
        out = summarize_args({"path": "/x", "content": "y" * 500})
        self.assertEqual(out["path"], "/x")
        self.assertIn("500 chars", out["content"])
        self.assertLess(len(out["content"]), 200)

    def test_non_dict_passthrough(self):
        self.assertEqual(summarize_args("nope"), "nope")


if __name__ == "__main__":
    unittest.main()
