# AIOS examples

Small apps built on the [AIOS SDK](../sdk/README.md). They target the Platform
API v1 — no HTTP, no host knowledge. Each is short and copy-pasteable.

Setup:

```bash
pip install ./sdk           # the SDK
make run                    # a running aiosd (or `make mock` for an offline demo)
```

| Example | What it shows |
|---------|---------------|
| [`quick_ask.py`](quick_ask.py) | one-shot `ask` |
| [`briefing.py`](briefing.py) | compose `ask` + `notify` (result reaches the bell/desktop) |
| [`notes_qa.py`](notes_qa.py) | `index` a folder, then answer grounded in it |

```bash
python examples/quick_ask.py "how do I free disk space?"
python examples/briefing.py
python examples/notes_qa.py ~/notes "what did I decide about the budget?"
```

The reusable examples (`briefing.run`, `notes_qa.run`) take an `AIOSClient` so
they're unit-tested against a real daemon in `sdk/tests/test_examples.py`.
