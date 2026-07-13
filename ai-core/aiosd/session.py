"""SessionManager — the AIOS seam over the login/session mechanism.

Isolating this (Constitution §II; matrix row #16) means *how the AIOS graphical
session is launched at login* is swappable. The current implementation targets
**greetd** (a minimal, AIOS-owned login), generating its config to launch the
AIOS Sway session (`aios-session`). A future AIOS-native greeter/login manager
implements the same interface.

Honesty note: greetd runs on the Linux target, not the macOS dev host — so the
**config generation** is unit-tested here; wiring greetd into a booted system is
validated on hardware (see docs/asahi-bringup.md). The generator is pure.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SessionManager(ABC):
    name = "base"

    @abstractmethod
    def session_command(self) -> str:
        """The command that launches the AIOS graphical session."""

    @abstractmethod
    def greeter_config(self, autologin_user: str | None = None) -> str:
        """The login-manager configuration text for the AIOS session."""


class GreetdSessionManager(SessionManager):
    """Generates a greetd config that presents/launches the AIOS session."""

    name = "greetd"

    def __init__(self, session_command: str = "aios-session", greeter: str = "tuigreet"):
        self._command = session_command
        self.greeter = greeter

    def session_command(self) -> str:
        return self._command

    def greeter_config(self, autologin_user: str | None = None) -> str:
        lines = [
            "# greetd config for the AIOS login session.",
            "# Install to /etc/greetd/config.toml (root), then enable greetd.",
            "",
            "[terminal]",
            "vt = 1",
            "",
            "[default_session]",
            f'command = "{self.greeter} --time --remember --cmd {self._command}"',
        ]
        if autologin_user:
            lines += [
                "",
                "# Autologin (single-user machine): launch the session directly.",
                "[initial_session]",
                f'command = "{self._command}"',
                f'user = "{autologin_user}"',
            ]
        return "\n".join(lines) + "\n"


def make_session_manager(session_command: str = "aios-session",
                         greeter: str = "tuigreet") -> SessionManager:
    """Select the session/login mechanism. greetd today; an AIOS greeter later."""
    return GreetdSessionManager(session_command=session_command, greeter=greeter)
