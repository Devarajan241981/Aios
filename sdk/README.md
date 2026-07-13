# AIOS SDK

A zero-dependency Python client for the **AIOS Platform API v1**. Write apps and
scripts against **AIOS**, not raw HTTP — and with no knowledge of the host OS or
kernel (the point of the Platform API boundary).

Versioned to the frozen v1 contract
([spec](../docs/architecture/04-platform-api-v1.md)).

## Install

```bash
pip install ./sdk          # or: cd sdk && pip install -e .
```

Requires a running `aiosd` (see the repo README). Standard-library only.

## Usage

```python
from aios_sdk import AIOSClient

aios = AIOSClient()                          # http://127.0.0.1:8765 by default
# aios = AIOSClient("http://127.0.0.1:8765", token="…")  # if auth is on

# ask
print(aios.ask("how do I free disk space?").reply)

# stream
for delta in aios.stream("write a haiku about local AI"):
    print(delta, end="", flush=True)

# semantic memory
aios.index(["/home/me/notes"])
for hit in aios.search("the Q3 budget"):
    print(hit.score, hit.source)

# sessions (persistent, resumable)
s = aios.create_session("work")
aios.ask("plan my launch", session=s.id)

# tools with the preview-before-run gate
r = aios.ask("write a file to ~/notes/x.txt", use_tools=True)
if r.needs_approval:
    print(r.pending[0]["preview"])
    r = aios.ask("write a file to ~/notes/x.txt", use_tools=True,
                 approved_signatures=r.signatures)   # or grant the tool to a session

# notifications
aios.notify("build done", level="success")
items, unread = aios.notifications(unread=True)
```

## Surface

`health` · `version` · `ask` · `stream` · `index` · `index_stats` · `search` ·
`tools` · `sessions` · `create_session` · `session` · `delete_session` · `grant` ·
`revoke` · `notify` · `notifications` · `mark_read` · `clear_notifications` ·
`audit`.

Errors: `APIError(status, message)`, `AIOSConnectionError`, base `AIOSError`.
