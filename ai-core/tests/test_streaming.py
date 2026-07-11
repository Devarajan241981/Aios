import json
import threading
import unittest
import urllib.request

from aiosd.assistant import Assistant
from aiosd.backends import Backend, MockBackend
from aiosd.config import Config
from aiosd.server import build_server


class _WholeReplyBackend(Backend):
    """Uses the base-class default stream_chat (single delta)."""

    name = "whole"

    def chat(self, messages, *, model, timeout):
        return "one two three"


class TestBackendStreaming(unittest.TestCase):
    def test_mock_deltas_rejoin_to_chat(self):
        b = MockBackend()
        msgs = [{"role": "user", "content": "hello there"}]
        deltas = list(b.stream_chat(msgs, model="m", timeout=1))
        self.assertGreater(len(deltas), 1)  # actually streamed in pieces
        self.assertEqual("".join(deltas), b.chat(msgs, model="m", timeout=1))

    def test_base_default_yields_single_delta(self):
        deltas = list(_WholeReplyBackend().stream_chat([], model="m", timeout=1))
        self.assertEqual(deltas, ["one two three"])


class TestAssistantStreaming(unittest.TestCase):
    def test_ask_stream_rejoins(self):
        a = Assistant(
            MockBackend(),
            Config.from_env({"AIOS_BACKEND": "mock"}),
            context_provider=lambda: {"host": "H"},
        )
        text = "".join(a.ask_stream("ping"))
        self.assertIn("ping", text)


class TestServerStreaming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = Config.from_env({"AIOS_BACKEND": "mock", "AIOS_PORT": "0",
                               "AIOS_DB_PATH": ":memory:"})
        cls.httpd = build_server(cfg)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.httpd.aios_state.storage.close()

    def _stream(self, payload):
        data = json.dumps({**payload, "stream": True}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/chat", data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        events = []
        with urllib.request.urlopen(req) as resp:
            content_type = resp.headers.get("Content-Type", "")
            for raw in resp:
                line = raw.decode().strip()
                if line.startswith("data:"):
                    body = line[len("data:"):].strip()
                    if body == "[DONE]":
                        break
                    events.append(json.loads(body))
        return content_type, events

    def test_sse_content_type_and_reassembly(self):
        content_type, events = self._stream({"prompt": "ping pong"})
        self.assertTrue(content_type.startswith("text/event-stream"))
        deltas = [e["delta"] for e in events if "delta" in e]
        self.assertIn("ping pong", "".join(deltas))

    def test_stream_ends_with_done_event(self):
        _, events = self._stream({"prompt": "hi"})
        self.assertTrue(events[-1].get("done") is True)
        self.assertIn("model", events[-1])


if __name__ == "__main__":
    unittest.main()
