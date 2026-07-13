"""AIOS SDK — a zero-dependency Python client for the AIOS Platform API v1.

    from aios_sdk import AIOSClient
    aios = AIOSClient()                    # http://127.0.0.1:8765 by default
    print(aios.ask("hello").reply)

Apps written against this SDK target AIOS, not HTTP, and have no knowledge of the
host OS or kernel — the whole point of the Platform API boundary.
"""

from .client import API_VERSION, AIOSClient
from .errors import AIOSConnectionError, AIOSError, APIError
from .models import ChatResult, Notification, SearchResult, Session

__version__ = "0.1.0"

__all__ = [
    "AIOSClient", "API_VERSION",
    "AIOSError", "AIOSConnectionError", "APIError",
    "ChatResult", "Notification", "SearchResult", "Session",
]
