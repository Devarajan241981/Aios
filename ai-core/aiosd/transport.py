"""Transport — the AIOS seam over how applications reach the service.

The Platform API (the v1 contract) is *what* apps say; the Transport is *how* the
bytes travel. Isolating this (Constitution §II; matrix row #23) means the same
frozen contract can ride a different medium later — a Unix socket today, AIOS
message-ports on our own kernel tomorrow — without touching request handling or
the contract.

Two implementations ship, which is what justifies the seam (Constitution §III.8 —
no speculative abstraction):

* :class:`TcpHttpTransport` — HTTP over loopback TCP (default; required by the
  browser web UI).
* :class:`UnixHttpTransport` — the *same* HTTP handler over a Unix-domain socket:
  no network port at all, access controlled by filesystem permissions (0600).

Both reuse the exact same request handler, so the endpoint logic is
transport-agnostic by construction.
"""

from __future__ import annotations

import os
import socket
import socketserver
from abc import ABC, abstractmethod
from http.server import ThreadingHTTPServer


class Transport(ABC):
    name = "base"

    @abstractmethod
    def create(self, handler) -> socketserver.BaseServer:
        """Build (and bind) a server that serves ``handler`` over this medium."""

    @abstractmethod
    def describe(self) -> str:
        """Human-readable address for logs."""


class TcpHttpTransport(Transport):
    name = "tcp"

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def create(self, handler) -> ThreadingHTTPServer:
        return ThreadingHTTPServer((self.host, self.port), handler)

    def describe(self) -> str:
        return f"http://{self.host}:{self.port}/"


class _UnixHttpServer(ThreadingHTTPServer):
    """ThreadingHTTPServer bound to an AF_UNIX socket with 0600 permissions."""

    address_family = socket.AF_UNIX

    def __init__(self, path: str, handler):
        self._path = path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        try:
            os.unlink(path)  # clear a stale socket from a prior run
        except OSError:
            pass
        super().__init__(path, handler)

    def server_bind(self):
        # Bind to the path directly; skip HTTPServer's host/port unpacking, which
        # assumes an (addr, port) tuple.
        socketserver.TCPServer.server_bind(self)
        self.server_name = "localhost"
        self.server_port = 0
        try:
            os.chmod(self._path, 0o600)  # only the owner may talk to the daemon
        except OSError:
            pass

    def server_close(self):
        super().server_close()
        try:
            os.unlink(self._path)
        except OSError:
            pass


class UnixHttpTransport(Transport):
    name = "unix"

    # AF_UNIX paths are capped by the OS (~104 bytes on macOS/BSD, 108 on Linux).
    MAX_PATH = 100

    def __init__(self, path: str):
        if len(os.fsencode(path)) > self.MAX_PATH:
            raise ValueError(
                f"socket path too long for a Unix socket ({len(path)} bytes): {path}\n"
                "Set AIOS_SOCKET_PATH to something short (e.g. under $XDG_RUNTIME_DIR "
                "or /tmp)."
            )
        self.path = path

    def create(self, handler) -> _UnixHttpServer:
        return _UnixHttpServer(self.path, handler)

    def describe(self) -> str:
        return f"http+unix://{self.path}"


def make_transport(config) -> Transport:
    """Select the transport. TCP by default; Unix socket via AIOS_TRANSPORT=unix."""
    if getattr(config, "transport", "tcp") == "unix":
        return UnixHttpTransport(config.socket_path)
    return TcpHttpTransport(config.host, config.port)
