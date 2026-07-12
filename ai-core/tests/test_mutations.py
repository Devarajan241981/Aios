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

    def test_overwrite_preview_shows_unified_diff(self):
        target = os.path.join(self.tmp.name, "diff.txt")
        with open(target, "w") as fh:
            fh.write("line1\nline2\nline3\n")
        text = self.reg.preview(
            "write_file",
            {"path": target, "content": "line1\nCHANGED\nline3\n"},
            self.ctx,
        )
        self.assertIn("Overwrite", text)
        self.assertIn("@@", text)          # a hunk header
        self.assertIn("-line2", text)      # removed line
        self.assertIn("+CHANGED", text)    # added line
        # still no side effect
        with open(target) as fh:
            self.assertEqual(fh.read(), "line1\nline2\nline3\n")

    def test_overwrite_identical_reports_no_changes(self):
        target = os.path.join(self.tmp.name, "same.txt")
        with open(target, "w") as fh:
            fh.write("unchanged\n")
        text = self.reg.preview("write_file", {"path": target, "content": "unchanged\n"}, self.ctx)
        self.assertIn("no changes", text)

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

    def test_move_and_delete_are_mutating(self):
        self.assertFalse(self.reg.get("move_file").safe)
        self.assertFalse(self.reg.get("delete_file").safe)

    def test_move_file(self):
        src = os.path.join(self.tmp.name, "a.txt")
        dst = os.path.join(self.tmp.name, "b.txt")
        with open(src, "w") as fh:
            fh.write("data")
        res = self.reg.execute("move_file", {"source": src, "destination": dst},
                               self.ctx, approve=True)
        self.assertTrue(res["ok"])
        self.assertFalse(os.path.exists(src))
        self.assertTrue(os.path.exists(dst))

    def test_move_outside_root_denied(self):
        src = os.path.join(self.tmp.name, "a.txt")
        with open(src, "w") as fh:
            fh.write("x")
        res = self.reg.execute("move_file", {"source": src, "destination": "/etc/evil"},
                               self.ctx, approve=True)
        self.assertFalse(res["ok"])
        self.assertIn("not allowed", res["error"])

    def test_delete_moves_to_trash(self):
        trash = os.path.join(self.tmp.name, "trash")
        ctx = ToolContext(config=Config.from_env(
            {"AIOS_ALLOWED_ROOTS": self.tmp.name, "AIOS_TRASH_PATH": trash}))
        victim = os.path.join(self.tmp.name, "victim.txt")
        with open(victim, "w") as fh:
            fh.write("bye")
        res = self.reg.execute("delete_file", {"path": victim}, ctx, approve=True)
        self.assertTrue(res["ok"])
        self.assertFalse(os.path.exists(victim))          # gone from original
        trashed = os.listdir(trash)
        self.assertEqual(len(trashed), 1)                 # recoverable in trash
        with open(os.path.join(trash, trashed[0])) as fh:
            self.assertEqual(fh.read(), "bye")

    def test_delete_blocked_without_approval(self):
        victim = os.path.join(self.tmp.name, "keep.txt")
        with open(victim, "w") as fh:
            fh.write("safe")
        res = self.reg.execute("delete_file", {"path": victim}, self.ctx)
        self.assertTrue(res["needs_approval"])
        self.assertTrue(os.path.exists(victim))           # untouched


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

    def test_granted_tool_auto_approves(self):
        result = self.agent.run([{"role": "user", "content": "write it"}],
                                granted_tools={"write_file"})
        self.assertEqual(result["status"], "complete")
        self.assertTrue(os.path.exists(self.target))

    def test_grant_of_other_tool_does_not_approve(self):
        result = self.agent.run([{"role": "user", "content": "write it"}],
                                granted_tools={"move_file"})
        self.assertEqual(result["status"], "needs_approval")
        self.assertFalse(os.path.exists(self.target))


class TestApprovalOverHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.target = os.path.join(cls.tmp.name, "http.txt")
        cls.audit_path = os.path.join(cls.tmp.name, "audit.log")
        cfg = Config.from_env({"AIOS_BACKEND": "mock", "AIOS_PORT": "0",
                               "AIOS_DB_PATH": ":memory:",
                               "AIOS_ALLOWED_ROOTS": cls.tmp.name,
                               "AIOS_AUDIT_PATH": cls.audit_path})
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

    def _audit(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/v1/audit") as resp:
            return json.loads(resp.read().decode())["events"]

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

        # the audit log records both the approval halt and the execution
        events = self._audit()
        kinds = [(e.get("event"), e.get("tool")) for e in events]
        self.assertIn(("pending", "write_file"), kinds)
        tool_events = [e for e in events if e.get("event") == "tool" and e.get("tool") == "write_file"]
        self.assertTrue(tool_events)
        self.assertTrue(tool_events[-1]["ok"])
        self.assertTrue(tool_events[-1]["approved"])


if __name__ == "__main__":
    unittest.main()
