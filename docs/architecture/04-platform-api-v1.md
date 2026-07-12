# AIOS Platform API — v1 (frozen)

The **Platform API is the application-facing boundary of AIOS** (see
[01-layered-architecture](01-layered-architecture.md)): the contract every
application targets. The web UI and the `aios` CLI are already pure clients of it;
the SDK and future native/third-party apps target the same surface.

Applications MUST use only this API. They MUST NOT use Linux, systemd, POSIX, or
any host facility directly (Constitution §I.3). An app cannot tell which kernel
exists — that is the point.

**Status: v1 frozen.** This is the Stage-1 exit criterion.

## Versioning & stability contract

- The **application data plane** lives under **`/v1/…`**. The path prefix *is* the
  contract version. `api_version` is also advertised in `/health` and `/version`.
- **Within v1, changes are additive only:** new endpoints, new **optional**
  request fields, new response fields. We will **never**, within v1: remove or
  rename a field, change a field's type, repurpose a value, or tighten
  validation in a breaking way.
- A **breaking change introduces `/v2`** served *alongside* `/v1`. `/v1` is
  supported for a published deprecation window after `/v2` ships.
- The [contract test suite](../../ai-core/tests/test_api_contract.py) pins these
  shapes. Drift fails CI. **The freeze is enforced by tests, not by good
  intentions.**

## Planes

| Plane | Endpoints | Guarantee |
|-------|-----------|-----------|
| **Application data** | `/v1/…` | Frozen v1 contract (this document) |
| **Operations** | `/health`, `/version`, `/config` | Stable & additive; liveness/introspection, not part of the app data contract |
| **Asset** | `/` | The web UI (HTML); not an API |

## Conventions

- Base URL: `http://127.0.0.1:8765` (loopback only by default).
- Requests/responses are JSON (`Content-Type: application/json`) unless streaming.
- **Auth:** if a token is configured, every endpoint except `/health` and `/`
  requires `Authorization: Bearer <token>`; otherwise `401 {"error": …}`.
- **Errors:** always `{"error": "<message>"}` with an appropriate status:
  `400` bad request · `401` unauthorized · `404` not found · `413` body too large
  · `500` internal · `502` backend/model failure.
- **Limits:** request bodies over `max_body_bytes` are rejected with `413`.

## Operations plane

### `GET /health`
```json
{ "status": "ok", "service": "aiosd", "version": "0.4.0", "api_version": 1,
  "backend": { "ok": true, "backend": "ollama", "models": ["…"] },
  "index": { "documents": 12, "embeddings": "hashing" },
  "tools": true }
```

### `GET /version`
`{ "version": "0.4.0", "api_version": 1, "python": "3.14.3" }`

### `GET /config`
Sanitized effective settings (the secret token is never returned; `token_set`
is a boolean). Operations plane — apps should not depend on its exact shape.

## Application data plane (`/v1`)

### `POST /v1/chat`
Request:
```json
{ "prompt": "…",           // required
  "session_id": "work",     // optional — persist & replay this session
  "history": [ … ],         // optional — used only when no session_id
  "stream": false,          // optional — SSE streaming (mutually exclusive w/ use_tools)
  "use_tools": false,       // optional — run the tool/agent loop
  "approve": false,         // optional — auto-approve mutating tools
  "approved_signatures": [] // optional — approve specific pending actions
}
```
Non-streaming response (`status: "complete"`):
```json
{ "reply": "…", "model": "llama3.2", "status": "complete",
  "steps": [ … ],            // present when use_tools
  "session_id": "work" }     // present when session_id given
```
Approval-required response (a mutating tool needs consent; **no side effects
happened**):
```json
{ "status": "needs_approval", "model": "…",
  "pending": [ { "tool": "write_file", "args": {…},
                 "preview": "…", "signature": "abc123…" } ],
  "steps": [ … ] }
```
Streaming response (`"stream": true`): `text/event-stream` of
`data: {"delta":"…"}` events, then `data: {"done":true,"model":"…","session_id":…}`,
then `data: [DONE]`. Mid-stream failures arrive as `data: {"error":"…"}`.

### `POST /v1/index`
`{ "paths": ["/abs/dir", …] }` → `{ "indexed": 12, "documents": 42 }`

### `GET /v1/index/stats`
`{ "documents": 42, "sources": ["/abs/file", …] }`

### `POST /v1/search`
`{ "query": "…", "k": 5 }` →
`{ "results": [ { "source": "/abs/file", "text": "…", "score": 0.87 }, … ] }`

### `GET /v1/tools`
`{ "enabled": true, "tools": [ { "name": "read_file", "description": "…", "safe": true }, … ] }`

### Sessions
- `GET /v1/sessions` → `{ "sessions": [ { "id", "title", "created_at", "updated_at", "messages" }, … ] }`
- `POST /v1/sessions` `{ "title"?: "…" }` → `201` `{ "id", "title", "created_at", "updated_at", "messages" }`
- `GET /v1/sessions/<id>` → `{ "session": {…}, "messages": [ { "role", "content" }, … ], "grants": ["write_file", …] }` (`404` if unknown)
- `DELETE /v1/sessions/<id>` → `{ "deleted": true }`
- `POST /v1/sessions/<id>/grants` `{ "tool": "write_file", "revoke"?: false }` → `{ "grants": [ … ] }`

### `GET /v1/audit?n=<N>`
`{ "events": [ { "ts", "event": "tool"|"pending"|"grant"|"revoke", "tool", … }, … ] }`

## Design notes

- **This surface is transport-shaped as HTTP today** but the *contract* is the
  data, not HTTP. The `Transport` seam (matrix #23) will let the same contract
  ride AIOS message-ports later without changing this document's semantics.
- **The tool/approval fields mirror the capability model** (preview-before-run,
  content-addressed approval, per-session grants) — the same security philosophy
  that runs from here down to the kernel design.
