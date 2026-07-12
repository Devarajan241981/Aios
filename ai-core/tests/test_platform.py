import unittest

from aiosd.context import gather_context
from aiosd.platform import Platform, current_platform
from aiosd.platform.posix import PosixPlatform


class TestPosixPlatform(unittest.TestCase):
    def setUp(self):
        self.p = PosixPlatform()

    def test_implements_interface(self):
        self.assertIsInstance(self.p, Platform)

    def test_hostname_and_username_nonempty(self):
        self.assertTrue(self.p.hostname())
        self.assertTrue(self.p.username())

    def test_os_description_includes_machine(self):
        self.assertIn("(", self.p.os_description())  # "... (aarch64)"

    def test_battery_is_str_or_none_and_never_raises(self):
        battery = self.p.battery()
        self.assertTrue(battery is None or isinstance(battery, str))


class TestCurrentPlatform(unittest.TestCase):
    def test_is_cached_singleton(self):
        self.assertIs(current_platform(), current_platform())

    def test_is_a_platform(self):
        self.assertIsInstance(current_platform(), Platform)


class TestContextGoesThroughHAL(unittest.TestCase):
    def test_context_shape_preserved(self):
        ctx = gather_context()
        for key in ("time", "user", "host", "os"):
            self.assertIn(key, ctx)


if __name__ == "__main__":
    unittest.main()
