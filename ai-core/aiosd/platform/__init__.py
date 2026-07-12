"""Platform HAL — the boundary that isolates the host OS from AIOS.

This is the concrete embodiment of the project's north star (see
``docs/architecture/01-layered-architecture.md``): **no AIOS component above this
layer talks to the host operating system directly.** Anything that is inherently
OS-specific — device facts, power, later: services, filesystem roots — is
obtained through the :class:`Platform` interface.

Today the only implementation is :class:`~aiosd.platform.posix.PosixPlatform`
(Linux in production; macOS during development). When AIOS eventually runs on its
own kernel, a new ``Platform`` implementation is added here and **nothing above
this layer changes**. That is the entire point of the boundary.

Keep this interface small and honest: add a method only when a real caller needs
to reach the host (Constitution §4 — no speculative abstraction).
"""

from __future__ import annotations

import functools
from abc import ABC, abstractmethod


class Platform(ABC):
    """The host-abstraction contract. Implementations must never raise."""

    name = "base"

    @abstractmethod
    def hostname(self) -> str:
        """Machine hostname (best-effort; returns a placeholder, never raises)."""

    @abstractmethod
    def username(self) -> str:
        """Current user name (best-effort)."""

    @abstractmethod
    def os_description(self) -> str:
        """Human-readable OS string, e.g. ``Linux 6.9 (aarch64)``."""

    @abstractmethod
    def battery(self) -> str | None:
        """Battery percentage as a string (e.g. ``"82%"``) or None if unknown."""


@functools.lru_cache(maxsize=1)
def current_platform() -> Platform:
    """Return the process-wide Platform. Selected here and nowhere else."""
    from .posix import PosixPlatform  # imported lazily to avoid an import cycle
    return PosixPlatform()
