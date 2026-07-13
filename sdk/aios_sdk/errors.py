"""Exceptions raised by the AIOS SDK."""

from __future__ import annotations


class AIOSError(Exception):
    """Base class for all SDK errors."""


class AIOSConnectionError(AIOSError):
    """The AIOS daemon could not be reached."""


class APIError(AIOSError):
    """The daemon returned an error response."""

    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"[{status}] {message}")
