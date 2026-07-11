import unittest

from aiosd.assistant import Assistant
from aiosd.backends import MockBackend
from aiosd.config import Config


class TestAssistant(unittest.TestCase):
    def setUp(self):
        self.assistant = Assistant(
            MockBackend(),
            Config.from_env({"AIOS_BACKEND": "mock"}),
            context_provider=lambda: {"time": "T", "host": "H"},
        )

    def test_build_messages_has_system_and_context(self):
        messages = self.assistant.build_messages("hi")
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("host: H", messages[0]["content"])
        self.assertEqual(messages[-1], {"role": "user", "content": "hi"})

    def test_history_included_in_order(self):
        history = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
        ]
        messages = self.assistant.build_messages("hi", history=history)
        self.assertEqual(len(messages), 4)  # system + 2 history + prompt
        self.assertEqual(messages[1:3], history)

    def test_ask_roundtrip(self):
        self.assertIn("hi", self.assistant.ask("hi"))


if __name__ == "__main__":
    unittest.main()
