import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from aiosd.agent import Agent
from aiosd.backends import Backend
from aiosd.config import Config
from aiosd.server import build_server
from aiosd.tools import ToolContext, default_registry, signature


class StatelessWriteBackend(Backend):
    """Requests one write_file call, then answers once a tool result exists.

    Stateless w.r.t. call count so re-running from the same prompt (as the HTTP
    approval flow does) reproduces the identical tool call every time.
    """

    def __init__(self, path, content):
        self.path = path
        self.content = content

    def chat(self, messages, *, model, timeout):
        return "ok"

    def chat_with_tools(self, messages, tools, *, model, timeout):
        if any(m.get("role") == "tool" for m in messages):
            return {"content": "Done.", "tool_calls": []}
        return {"content": None, "tool_calls": [
            {"id": "1", "name": "write_file",
             "arguments": {"path": self.path, "content": self.content}}
        ]}


class TestMutatingTools(unittest.TestCase):
    def setUp(self):
        self.reg = default_registry()
        self.tmp = tempfile.TemporaryDirectory()
        self.ctx = ToolContext(config=Config.from_env({"AIOS_ALLOWED_ROOTS": self.tmp.name}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_file_is_mutating(self):
        self.assertFalse(self.reg.get("write_file").safe)
        self.assertFalse(self.reg.get("run_command").safe)

    def test_write_file_blocked_without_approval(self):
        target = os.path.join(self.tmp.name, "out.txt")
        res = self.reg.execute("write_file", {"path": target, "content": "hi"}, self.ctx)
        self.assertFalse(res["ok"])
        self.assertTrue(res["needs_approval"])
        self.assertFalse(os.path.exists(target))  # nothing written

    def test_write_file_runs_with_approval(self):
        target = os.path.join(self.tmp.name, "out.txt")
        res = self.reg.execute("write_file", {"path": target, "content": "hello"},
                               self.ctx, approve=True)
        self.assertTrue(res["ok"])
        with open(target) as fh:
            self.assertEqual(fh.read(), "hello")

    def test_write_file_outside_root_denied(self):
        ctx = ToolContext(config=Config.from_env({}))
        res = ctx and self.reg.execute("write_file",
                                       {"path": "/etc/aios_hack", "content": "x"},
                                       ctx, approve=True)
        self.assertFalse(res["ok"])
        self.assertIn("not allowed", res["error"])

    def test_write_file_preview_has_no_side_effect(self):
        target = os.path.join(self.tmp.name, "preview.txt")
        text = self.reg.preview("write_file", {"path": target, "content": "abc"}, self.ctx)
        self.assertIn("Create", text)
        self.assertFalse(os.path.exists(target))

    def test_run_command_allowlist(self):
        ok = self.reg.execute("run_command", {"command": "echo hello"}, self.ctx, approve=True)
        self.assertTrue(ok["ok"])
        self.assertIn("hello", ok["result"])
        denied = self.reg.execute("run_command", {"command": "rm -rf /"}, self.ctx, approve=True)
        self.assertFalse(denied["ok"])
        self.assertIn("not allowed", denied["error"])

    def test_signature_is_stable_and_distinct(self):
        a = signature("write_file", {"path": "/a", "content": "x"})
        b = signature("write_file", {"content": "x", "path": "/a"})  # key order
        c = signature("write_file", {"path": "/b", "content": "x"})
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


class TestAgentApproval(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = os.path.join(self.tmp.name, "agent.txt")
        self.cfg = Config.from_env({"AIOS_ALLOWED_ROOTS": self.tmp.name})
        self.ctx = ToolContext(config=self.cfg)
        self.backend = StatelessWriteBackend(self.target, "written by agent")
        self.agent = Agent(self.backend, default_registry(), self.ctx, self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def test_halts_and_does_not_write(self):
        result = self.agent.run([{"role": "user", "content": "write it"}])
        self.assertEqual(result["status"], "needs_approval")
        self.assertEqual(result["pending"][0]["tool"], "write_file")
        self.assertIn("signature", result["pending"][0])
        self.assertFalse(os.path.exists(self.target))

    def test_executes_after_signature_approval(self):
        sig = signature("write_file", {"path": self.target, "content": "written by agent"})
        result = self.agent.run([{"role": "user", "content": "write it"}], approved={sig})
        self.assertEqual(result["status"], "complete")
        self.assertTrue(os.path.exists(self.target))

    def test_approve_all(self):
        result = self.agent.run([{"role": "user", "content": "write it"}], approve_all=True)
        self.assertEqual(result["status"], "complete")
        self.assertTrue(os.path.exists(self.target))


class TestApprovalOverHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.target = os.path.join(cls.tmp.name, "http.txt")
        cfg = Config.from_env({"AIOS_BACKEND": "mock", "AIOS_PORT": "0",
                               "AIOS_DB_PATH": ":memory:",
                               "AIOS_ALLOWED_ROOTS": cls.tmp.name})
        cls.httpd = build_server(cfg)
        # inject a backend that will request a write_file tool call
        cls.httpd.aios_state.agent.backend = StatelessWriteBackend(cls.target, "hello http")
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.httpd.aios_state.storage.close()
        cls.tmp.cleanup()

    def _post(self, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat",
                                     data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())

    def test_two_step_approval(self):
        # step 1: request halts for approval, nothing written
        code, body = self._post({"prompt": "please write the file", "use_tools": True})
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "needs_approval")
        pending = body["pending"][0]
        self.assertEqual(pending["tool"], "write_file")
        self.assertFalse(os.path.exists(self.target))

        # step 2: approve the exact signature -> executes, file written
        code, body = self._post({"prompt": "please write the file", "use_tools": True,
                                 "approved_signatures": [pending["signature"]]})
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "complete")
        self.assertTrue(os.path.exists(self.target))
        with open(self.target) as fh:
            self.assertEqual(fh.read(), "hello http")


if __name__ == "__main__":
    unittest.main()
