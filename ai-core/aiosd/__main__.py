"""Entrypoint: ``python -m aiosd`` starts the daemon."""

from .server import serve

if __name__ == "__main__":
    serve()
