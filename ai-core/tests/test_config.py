import os
import tempfile
import unittest

from aiosd.config import Config, load_config


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

    def test_redacted_dict_hides_token(self):
        d = Config.from_env({"AIOS_TOKEN": "secret"}).redacted_dict()
        self.assertNotIn("token", d)
        self.assertTrue(d["token_set"])
        self.assertIn("port", d)


class TestLoadConfig(unittest.TestCase):
    def _write(self, text):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "config.toml")
        with open(path, "w") as fh:
            fh.write(text)
        return path

    def test_reads_values_from_file(self):
        path = self._write('port = 9000\nmodel = "phi3"\n')
        c = load_config(env={}, path=path)
        self.assertEqual(c.port, 9000)
        self.assertEqual(c.model, "phi3")

    def test_env_overrides_file(self):
        path = self._write("port = 9000\n")
        c = load_config(env={"AIOS_PORT": "7000"}, path=path)
        self.assertEqual(c.port, 7000)

    def test_aios_table_supported(self):
        path = self._write('[aios]\nport = 9100\n')
        self.assertEqual(load_config(env={}, path=path).port, 9100)

    def test_missing_file_uses_defaults(self):
        c = load_config(env={}, path="/no/such/config.toml")
        self.assertEqual(c.port, 8765)

    def test_invalid_toml_is_ignored(self):
        path = self._write("port = = broken\n")
        self.assertEqual(load_config(env={}, path=path).port, 8765)

    def test_bool_and_list_values(self):
        path = self._write('tools = false\nallowed_commands = ["git", "rg"]\n')
        c = load_config(env={}, path=path)
        self.assertFalse(c.tools_enabled)
        self.assertIn("git", c.allowed_commands)
        self.assertIn("rg", c.allowed_commands)


if __name__ == "__main__":
    unittest.main()
