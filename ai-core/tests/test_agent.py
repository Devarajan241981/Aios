import unittest

from aiosd.agent import Agent
from aiosd.backends import Backend, MockBackend
from aiosd.config import Config
from aiosd.tools import ToolContext, default_registry


class ScriptedBackend(Backend):
    """Returns pre-scripted chat_with_tools responses, in order."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def chat(self, messages, *, model, timeout):
        return "unused"

    def chat_with_tools(self, messages, tools, *, model, timeout):
        step = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        return step


class TestAgent(unittest.TestCase):
    def setUp(self):
        self.cfg = Config.from_env({"AIOS_BACKEND": "mock"})
        self.ctx = ToolContext(config=self.cfg,
                               context_provider=lambda: {"os": "TestOS"})

    def test_executes_tool_then_answers(self):
        script = [
            {"content": None,
             "tool_calls": [{"id": "1", "name": "current_time", "arguments": {}}]},
            {"content": "Here is the time.", "tool_calls": []},
        ]
        agent = Agent(ScriptedBackend(script), default_registry(), self.ctx, self.cfg)
        result = agent.run([{"role": "user", "content": "what time is it?"}])
        self.assertEqual(result["reply"], "Here is the time.")
        self.assertEqual(len(result["steps"]), 1)
        self.assertEqual(result["steps"][0]["tool"], "current_time")
        self.assertTrue(result["steps"][0]["result"]["ok"])

    def test_stops_at_max_steps(self):
        looping = [{"content": None,
                    "tool_calls": [{"id": "1", "name": "current_time", "arguments": {}}]}]
        agent = Agent(ScriptedBackend(looping), default_registry(), self.ctx, self.cfg,
                      max_steps=3)
        result = agent.run([{"role": "user", "content": "loop"}])
        self.assertEqual(len(result["steps"]), 3)  # one per step, then stop
        self.assertIn("tool-step limit", result["reply"])

    def test_plain_backend_answers_without_tools(self):
        agent = Agent(MockBackend(), default_registry(), self.ctx, self.cfg)
        result = agent.run([{"role": "user", "content": "hello"}])
        self.assertIn("hello", result["reply"])
        self.assertEqual(result["steps"], [])


if __name__ == "__main__":
    unittest.main()
