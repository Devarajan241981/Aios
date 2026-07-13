import unittest

from aiosd.session import GreetdSessionManager, SessionManager, make_session_manager


class TestGreetdSessionManager(unittest.TestCase):
    def setUp(self):
        self.sm = GreetdSessionManager()

    def test_is_session_manager(self):
        self.assertIsInstance(self.sm, SessionManager)

    def test_session_command_default(self):
        self.assertEqual(self.sm.session_command(), "aios-session")

    def test_config_has_session_and_greeter(self):
        cfg = self.sm.greeter_config()
        self.assertIn("aios-session", cfg)
        self.assertIn("tuigreet", cfg)
        self.assertIn("[default_session]", cfg)
        self.assertNotIn("[initial_session]", cfg)  # no autologin by default

    def test_autologin_adds_initial_session(self):
        cfg = self.sm.greeter_config(autologin_user="alice")
        self.assertIn("[initial_session]", cfg)
        self.assertIn('user = "alice"', cfg)

    def test_custom_greeter_and_command(self):
        sm = GreetdSessionManager(session_command="aios-session", greeter="gtkgreet")
        cfg = sm.greeter_config()
        self.assertIn("gtkgreet", cfg)
        self.assertNotIn("tuigreet", cfg)


class TestFactory(unittest.TestCase):
    def test_returns_session_manager(self):
        self.assertIsInstance(make_session_manager(), SessionManager)


if __name__ == "__main__":
    unittest.main()
