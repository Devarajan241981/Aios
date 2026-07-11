import datetime
import unittest

from aiosd.statusline import fetch_health, render_blocks

WHEN = datetime.datetime(2026, 7, 12, 9, 5)


def _names(blocks):
    return [b["name"] for b in blocks]


class TestRenderBlocks(unittest.TestCase):
    def test_healthy(self):
        health = {"backend": {"backend": "ollama", "ok": True},
                  "index": {"documents": 12}}
        blocks = render_blocks(health, WHEN, "82%")
        names = _names(blocks)
        self.assertEqual(names[0], "aios")            # the launcher button first
        self.assertIn("backend", names)
        self.assertIn("index", names)
        self.assertIn("battery", names)
        self.assertIn("clock", names)
        backend = next(b for b in blocks if b["name"] == "backend")
        self.assertEqual(backend["full_text"], "ollama")
        self.assertEqual(next(b for b in blocks if b["name"] == "index")["full_text"], "12 docs")

    def test_offline_daemon(self):
        blocks = render_blocks({}, WHEN, None)
        backend = next(b for b in blocks if b["name"] == "backend")
        self.assertIn("offline", backend["full_text"])
        # no index/battery blocks when there's no data
        self.assertNotIn("index", _names(blocks))
        self.assertNotIn("battery", _names(blocks))

    def test_backend_down(self):
        health = {"backend": {"backend": "ollama", "ok": False}, "index": {"documents": 0}}
        backend = next(b for b in render_blocks(health, WHEN, None)
                       if b["name"] == "backend")
        self.assertIn("offline", backend["full_text"])

    def test_no_null_keys(self):
        # i3bar rejects null values; ensure they're stripped
        for block in render_blocks({"backend": {"backend": "mock", "ok": True}}, WHEN, None):
            self.assertNotIn(None, block.values())

    def test_clock_formatting(self):
        clock = next(b for b in render_blocks({}, WHEN, None) if b["name"] == "clock")
        self.assertIn("09:05", clock["full_text"])


class TestFetchHealth(unittest.TestCase):
    def test_unreachable_returns_empty(self):
        # nothing is listening here; must not raise
        self.assertEqual(fetch_health("http://127.0.0.1:9", timeout=0.3), {})


if __name__ == "__main__":
    unittest.main()
