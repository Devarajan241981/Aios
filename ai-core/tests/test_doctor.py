import io
import os
import unittest

from aiosd.doctor import FAIL, OK, WARN, evaluate, render


def probe(**overrides):
    base = {
        "base_url": "http://127.0.0.1:8765",
        "reachable": True,
        "health": {
            "version": "0.3.0",
            "backend": {"backend": "ollama", "ok": True, "models": ["llama3.2:latest"]},
            "index": {"documents": 3},
        },
        "config": {"model": "llama3.2", "backend": "ollama",
                   "tools_enabled": True, "audit_enabled": True, "token_set": False},
        "config_status": 200,
        "sessions_status": 200,
        "tools": {"enabled": True, "tools": [1, 2, 3]},
        "python": "3.14.3",
        "path": os.pathsep.join(["/usr/bin", "/home/me/.local/bin"]),
        "home_bin": "/home/me/.local/bin",
        "ollama_bin": "/usr/local/bin/ollama",
    }
    base.update(overrides)
    return base


def by_name(checks):
    return {c["name"]: c for c in checks}


class TestEvaluate(unittest.TestCase):
    def test_all_healthy(self):
        c = by_name(evaluate(probe()))
        self.assertEqual(c["daemon"]["status"], OK)
        self.assertEqual(c["backend"]["status"], OK)
        self.assertEqual(c["model"]["status"], OK)
        self.assertEqual(c["path"]["status"], OK)
        self.assertEqual(c["ollama"]["status"], OK)

    def test_daemon_unreachable_skips_dependent_checks(self):
        c = by_name(evaluate(probe(reachable=False, health=None)))
        self.assertEqual(c["daemon"]["status"], FAIL)
        self.assertNotIn("backend", c)
        self.assertNotIn("index", c)

    def test_backend_down_warns(self):
        p = probe()
        p["health"]["backend"]["ok"] = False
        self.assertEqual(by_name(evaluate(p))["backend"]["status"], WARN)

    def test_model_not_pulled_warns(self):
        p = probe()
        p["health"]["backend"]["models"] = ["mistral:latest"]
        self.assertEqual(by_name(evaluate(p))["model"]["status"], WARN)

    def test_empty_index_warns(self):
        p = probe()
        p["health"]["index"]["documents"] = 0
        self.assertEqual(by_name(evaluate(p))["index"]["status"], WARN)

    def test_path_missing_warns(self):
        self.assertEqual(by_name(evaluate(probe(path="/usr/bin")))["path"]["status"], WARN)

    def test_old_python_fails(self):
        self.assertEqual(by_name(evaluate(probe(python="3.9.6")))["python"]["status"], FAIL)

    def test_ollama_missing_warns_when_backend_ollama(self):
        c = by_name(evaluate(probe(ollama_bin=None)))
        self.assertEqual(c["ollama"]["status"], WARN)


class TestRender(unittest.TestCase):
    def test_failure_exit_code(self):
        out = io.StringIO()
        code = render([{"status": FAIL, "name": "daemon", "message": "down"}], out)
        self.assertEqual(code, 1)
        self.assertIn("daemon: down", out.getvalue())

    def test_success_exit_code(self):
        code = render([{"status": OK, "name": "python", "message": "fine"}], io.StringIO())
        self.assertEqual(code, 0)

    def test_counts_summary(self):
        out = io.StringIO()
        render([{"status": OK, "name": "a", "message": "m"},
                {"status": WARN, "name": "b", "message": "m"}], out)
        self.assertIn("1 ok", out.getvalue())
        self.assertIn("1 warning", out.getvalue())


if __name__ == "__main__":
    unittest.main()
