import unittest

from aiosd.backends import BackendError, MockBackend, make_backend
from aiosd.config import Config


class TestMockBackend(unittest.TestCase):
    def test_echoes_last_user_turn(self):
        out = MockBackend().chat(
            [{"role": "system", "content": "s"}, {"role": "user", "content": "hello"}],
            model="m",
            timeout=1,
        )
        self.assertIn("hello", out)
        self.assertIn("mock", out)

    def test_health_ok(self):
        self.assertTrue(MockBackend().health()["ok"])


class TestFactory(unittest.TestCase):
    def test_make_mock(self):
        b = make_backend(Config.from_env({"AIOS_BACKEND": "mock"}))
        self.assertIsInstance(b, MockBackend)

    def test_unknown_backend_raises(self):
        with self.assertRaises(BackendError):
            make_backend(Config.from_env({"AIOS_BACKEND": "nope"}))


if __name__ == "__main__":
    unittest.main()
