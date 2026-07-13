"""Test the `aios` CLI end-to-end against a real aiosd.

Loads bin/aios as a module and drives `main([...])`, capturing stdout/stderr and
exit codes. This is the CLI's safety net — it protects the refactor of the CLI
onto the SDK, and any future CLI change.
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import os
import sys
import tempfile
import threading
import unittest

_SDK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO = os.path.dirname(_SDK_DIR)
sys.path.insert(0, _SDK_DIR)
sys.path.insert(0, os.path.join(_REPO, "ai-core"))

from aiosd.config import Config  # noqa: E402
from aiosd.server import build_server  # noqa: E402


def _load_cli():
    path = os.path.join(_REPO, "bin", "aios")  # a script with no .py extension
    loader = importlib.machinery.SourceFileLoader("aios_cli", path)
    spec = importlib.util.spec_from_loader("aios_cli", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class TestCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cli = _load_cli()
        cls.tmp = tempfile.TemporaryDirectory()
        d = cls.tmp.name
        cfg = Config.from_env({"AIOS_BACKEND": "mock", "AIOS_PORT": "0",
                               "AIOS_DB_PATH": ":memory:", "AIOS_AUDIT": "off",
                               "AIOS_AUDIT_PATH": os.path.join(d, "audit.log"),
                               "AIOS_NOTIFY_DESKTOP": "off",
                               "AIOS_NOTIFICATIONS_PATH": os.path.join(d, "n.json"),
                               "AIOS_INDEX_PATH": os.path.join(d, "index.json")})
        cls.httpd = build_server(cfg)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.httpd.aios_state.storage.close()
        cls.tmp.cleanup()

    def run_cli(self, argv, port=None):
        os.environ["AIOS_PORT"] = str(port if port is not None else self.port)
        os.environ.pop("AIOS_TOKEN", None)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = self.cli.main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_status(self):
        code, out, _ = self.run_cli(["status"])
        self.assertEqual(code, 0)
        self.assertIn('"status": "ok"', out)

    def test_ask(self):
        code, out, _ = self.run_cli(["ask", "ping"])
        self.assertEqual(code, 0)
        self.assertIn("ping", out)

    def test_tools(self):
        code, out, _ = self.run_cli(["tools"])
        self.assertEqual(code, 0)
        self.assertIn("read_file", out)

    def test_search(self):
        # the shared daemon's index state varies with test order; just assert the
        # command runs cleanly (no error on stderr, exit 0).
        code, _, err = self.run_cli(["search", "anything"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

    def test_index(self):
        code, out, _ = self.run_cli(["index", "--stats"])
        self.assertEqual(code, 0)
        self.assertIn("documents:", out)
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write("the budget is fifty thousand")
            path = fh.name
        try:
            code, out, _ = self.run_cli(["index", path])
            self.assertEqual(code, 0)
            self.assertIn("indexed", out)
        finally:
            os.remove(path)

    def test_sessions_grant_history(self):
        code, out, _ = self.run_cli(["grant", "cli-sess", "write_file"])
        self.assertEqual(code, 0)
        self.assertIn("granted", out)
        _, out, _ = self.run_cli(["sessions"])
        self.assertIn("cli-sess", out)
        code, _, _ = self.run_cli(["history", "cli-sess"])
        self.assertEqual(code, 0)

    def test_notifications_flow(self):
        code, out, _ = self.run_cli(["notify", "hello there", "--level", "success"])
        self.assertEqual(code, 0)
        self.assertIn("notified", out)
        _, out, _ = self.run_cli(["notifications"])
        self.assertIn("hello there", out)
        code, out, _ = self.run_cli(["notifications", "--read"])
        self.assertIn("marked", out)
        code, out, _ = self.run_cli(["notifications", "--clear"])
        self.assertIn("cleared", out)

    def test_audit_empty(self):
        code, out, _ = self.run_cli(["audit"])
        self.assertEqual(code, 0)
        self.assertIn("no tool activity", out)

    def test_config(self):
        code, out, _ = self.run_cli(["config"])
        self.assertEqual(code, 0)
        self.assertIn("effective settings", out)

    def test_unreachable_daemon(self):
        code, _, err = self.run_cli(["status"], port=9)  # nothing listening
        self.assertEqual(code, 1)
        self.assertIn("cannot reach", err.lower())


if __name__ == "__main__":
    unittest.main()
