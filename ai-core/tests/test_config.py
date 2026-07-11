import unittest

from aiosd.config import Config


class TestConfig(unittest.TestCase):
    def test_defaults(self):
        c = Config.from_env({})
        self.assertEqual(c.backend, "ollama")
        self.assertEqual(c.port, 8765)
        self.assertEqual(c.host, "127.0.0.1")

    def test_env_override(self):
        c = Config.from_env({"AIOS_PORT": "9999", "AIOS_BACKEND": "mock", "AIOS_MODEL": "x"})
        self.assertEqual(c.port, 9999)
        self.assertEqual(c.backend, "mock")
        self.assertEqual(c.model, "x")

    def test_ollama_url_trailing_slash_stripped(self):
        c = Config.from_env({"AIOS_OLLAMA_URL": "http://host:1234/"})
        self.assertEqual(c.ollama_url, "http://host:1234")


if __name__ == "__main__":
    unittest.main()
