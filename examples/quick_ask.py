#!/usr/bin/env python3
"""One-shot: ask AIOS a question and print the reply.

    python examples/quick_ask.py "how do I free up disk space?"

Requires the AIOS SDK (`pip install ./sdk`) and a running `aiosd`.
"""

import sys

from aios_sdk import AIOSClient


def main() -> int:
    prompt = " ".join(sys.argv[1:]).strip() or "hello"
    print(AIOSClient().ask(prompt).reply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
