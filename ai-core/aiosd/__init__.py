"""AIOS AI-core daemon (aiosd).

The always-on, on-device assistant service at the heart of AIOS. Runs entirely
locally; no user data leaves the machine by default.
"""

__version__ = "0.4.0"

# The AIOS Platform API contract version — the frozen, app-facing data plane
# lives under /v1. Bumped only for a breaking change (which introduces /v2
# alongside /v1). See docs/architecture/04-platform-api-v1.md.
API_VERSION = 1
