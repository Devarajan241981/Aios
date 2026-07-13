import unittest

from aiosd.packages import (
    FlatpakPackageManager,
    NullPackageManager,
    PackageManager,
    _parse_columns,
    make_package_manager,
)


class TestParsing(unittest.TestCase):
    def test_parse_columns(self):
        out = "org.mozilla.firefox\tFirefox\t120.0\norg.gnome.TextEditor\tText Editor\t45.0\n"
        rows = _parse_columns(out, ["id", "name", "version"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {"id": "org.mozilla.firefox", "name": "Firefox", "version": "120.0"})
        self.assertEqual(rows[1]["name"], "Text Editor")

    def test_parse_columns_missing_fields(self):
        rows = _parse_columns("only.id\n", ["id", "name", "version"])
        self.assertEqual(rows[0], {"id": "only.id", "name": "", "version": ""})

    def test_parse_columns_skips_blank_lines(self):
        self.assertEqual(_parse_columns("\n\n", ["id"]), [])


class TestFlatpakDegradation(unittest.TestCase):
    """On a host without flatpak (e.g. macOS), every op degrades gracefully."""

    def setUp(self):
        self.pm = FlatpakPackageManager(flatpak="")  # force "not installed"

    def test_is_package_manager_but_unavailable(self):
        self.assertIsInstance(self.pm, PackageManager)
        self.assertFalse(self.pm.available)

    def test_ops_return_clear_error(self):
        for res in (self.pm.list_installed(),
                    self.pm.search("firefox"),
                    self.pm.install("org.x.Y"),
                    self.pm.remove("org.x.Y")):
            self.assertFalse(res["ok"])
            self.assertIn("flatpak is not installed", res["error"])


class TestNullPackageManager(unittest.TestCase):
    def test_all_ops_unavailable(self):
        pm = NullPackageManager()
        self.assertFalse(pm.available)
        for res in (pm.list_installed(), pm.search("x"),
                    pm.install("a"), pm.remove("a")):
            self.assertFalse(res["ok"])


class TestFactory(unittest.TestCase):
    def test_returns_package_manager(self):
        self.assertIsInstance(make_package_manager(), PackageManager)


if __name__ == "__main__":
    unittest.main()
