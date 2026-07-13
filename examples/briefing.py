#!/usr/bin/env python3
"""A tiny AIOS app: ask for a briefing and post it to the notification center.

Composes two AIOS capabilities through the SDK — the assistant and notifications
— so the result reaches you (bell + desktop). Pair it with a schedule to get a
morning briefing:

    python examples/briefing.py
    # or on the Linux target:
    aios schedule add briefing --at "daily 08:00" --prompt "..."   # (uses the CLI)
"""

from aios_sdk import AIOSClient

DEFAULT_PROMPT = "Give me a one-line status of my machine and anything I should know."


def run(aios: AIOSClient, prompt: str = DEFAULT_PROMPT) -> str:
    """Ask for a briefing, notify with it, and return the text. Testable."""
    reply = aios.ask(prompt).reply
    aios.notify("Briefing", body=reply, level="info", source="briefing")
    return reply


if __name__ == "__main__":
    print(run(AIOSClient()))
