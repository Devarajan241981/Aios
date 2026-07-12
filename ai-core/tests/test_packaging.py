import os
import subprocess
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SHELL_SCRIPTS = [
    "packaging/desktop/aios-shell",
    "packaging/desktop/aios-session",
    "packaging/desktop/aios-overlay",
    "packaging/desktop/aios-overlay-toggle",
    "packaging/desktop/aios-launch",
    "scripts/install.sh",
    "scripts/uninstall.sh",
    "scripts/asahi-bringup.sh",
]

OTHER_FILES = [
    "packaging/desktop/sway/config",
    "packaging/desktop/aios.desktop",
    "packaging/systemd/aiosd.service",
    "docs/asahi-bringup.md",
]


def _read(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
        return fh.read()


class TestPackagingFilesExist(unittest.TestCase):
    def test_all_present_and_nonempty(self):
        for rel in SHELL_SCRIPTS + OTHER_FILES:
            path = os.path.join(REPO, rel)
            self.assertTrue(os.path.exists(path), f"missing: {rel}")
            self.assertGreater(os.path.getsize(path), 0, f"empty: {rel}")

    def test_shell_scripts_are_executable(self):
        for rel in SHELL_SCRIPTS:
            self.assertTrue(os.access(os.path.join(REPO, rel), os.X_OK),
                            f"not executable: {rel}")


class TestShellSyntax(unittest.TestCase):
    def test_scripts_pass_bash_n(self):
        for rel in SHELL_SCRIPTS:
            result = subprocess.run(
                ["bash", "-n", os.path.join(REPO, rel)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0,
                             f"syntax error in {rel}:\n{result.stderr}")


class TestPackagingContent(unittest.TestCase):
    def test_shell_launches_ui(self):
        shell = _read("packaging/desktop/aios-shell")
        self.assertIn("/health", shell)
        self.assertIn("8765", shell)
        self.assertIn("--kiosk", shell)

    def test_sway_starts_daemon_and_shell(self):
        cfg = _read("packaging/desktop/sway/config")
        self.assertIn("aiosd.service", cfg)
        self.assertIn("aios-shell", cfg)

    def test_sway_binds_overlay_hotkey(self):
        cfg = _read("packaging/desktop/sway/config")
        self.assertIn("$mod+space", cfg)
        self.assertIn("aios-overlay-toggle", cfg)

    def test_overlay_launcher_runs_overlay(self):
        launcher = _read("packaging/desktop/aios-overlay")
        self.assertIn("aios overlay", launcher)
        self.assertIn("aios-overlay", launcher)  # stable app_id

    def test_sway_binds_app_launcher(self):
        cfg = _read("packaging/desktop/sway/config")
        self.assertIn("$mod+d", cfg)
        self.assertIn("aios-launch", cfg)

    def test_desktop_entry_runs_session(self):
        entry = _read("packaging/desktop/aios.desktop")
        self.assertIn("Exec=aios-session", entry)
        self.assertIn("Name=AIOS", entry)

    def test_installer_wires_service_and_cli(self):
        inst = _read("scripts/install.sh")
        self.assertIn("aiosd.service", inst)
        self.assertIn("bin/aios", inst)
        self.assertIn("--dry-run", inst)

    def test_sway_has_status_bar(self):
        cfg = _read("packaging/desktop/sway/config")
        self.assertIn("bar {", cfg)
        self.assertIn("status_command aios-statusline", cfg)

    def test_installer_generates_statusline(self):
        inst = _read("scripts/install.sh")
        self.assertIn("aios-statusline", inst)
        self.assertIn("aiosd.statusline", inst)


if __name__ == "__main__":
    unittest.main()
