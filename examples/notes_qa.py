#!/usr/bin/env python3
"""Index a folder into AIOS semantic memory, then answer a question grounded in it.

    python examples/notes_qa.py ~/notes "what did I decide about the budget?"
"""

import sys

from aios_sdk import AIOSClient


def run(aios: AIOSClient, folder: str, question: str) -> str:
    """Index `folder`, then ask `question`. Returns the grounded reply. Testable."""
    aios.index([folder])
    return aios.ask(question).reply


if __name__ == "__main__":
    aios = AIOSClient()
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    question = " ".join(sys.argv[2:]) or "What is this about?"
    print(run(aios, folder, question))
