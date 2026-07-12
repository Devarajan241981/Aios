"""``aios doctor`` — diagnose an AIOS setup and say what to fix.

Split into three pieces so the logic is testable:

* ``gather``   — probe the daemon (HTTP) and the local machine; returns raw data.
* ``evaluate`` — pure: turn that probe data into a list of checks.
* ``render``   — print the checks and return an exit code (1 if anything failed).
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import urllib.error
import urllib.request

OK, WARN, FAIL, INFO = "ok", "warn", "fail", "info"

_SYMBOLS = {OK: ("✓", "32"), WARN: ("!", "33"), FAIL: ("✗", "31"), INFO: ("·", "36")}


def _get(base_url, path, env, timeout=4):
    req = urllib.request.Request(base_url.rstrip("/") + path)
    token = env.get("AIOS_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception:
        return None, None


def gather(base_url, env) -> dict:
    health_status, health = _get(base_url, "/health", env)
    config_status, config = _get(base_url, "/config", env)
    sessions_status, _ = _get(base_url, "/v1/sessions", env)
    _, tools = _get(base_url, "/v1/tools", env)
    return {
        "base_url": base_url,
        "reachable": health_status == 200,
        "health": health,
        "config": config,
        "config_status": config_status,
        "sessions_status": sessions_status,
        "tools": tools,
        "python": platform.python_version(),
        "path": env.get("PATH", ""),
        "home_bin": os.path.join(os.path.expanduser("~"), ".local", "bin"),
        "ollama_bin": shutil.which("ollama"),
    }


def evaluate(p: dict) -> list:
    checks = []

    def add(status, name, message):
        checks.append({"status": status, "name": name, "message": message})

    version = tuple(int(x) for x in p["python"].split(".")[:2])
    add(OK if version >= (3, 11) else FAIL, "python",
        f"Python {p['python']}" + ("" if version >= (3, 11) else " (need >= 3.11)"))

    if not p["reachable"]:
        add(FAIL, "daemon",
            f"not reachable at {p['base_url']} — start it with `make run` or `aiosd`")
    else:
        health = p["health"] or {}
        add(OK, "daemon", f"reachable at {p['base_url']}, version {health.get('version', '?')}")

        backend = health.get("backend") or {}
        bname = backend.get("backend", "?")
        if backend.get("ok", False):
            add(OK, "backend", f"{bname} responding")
        else:
            hint = " — run `ollama serve` and `ollama pull <model>`" if bname == "ollama" else ""
            add(WARN, "backend", f"{bname} not responding{hint}")

        cfg = p["config"] or {}
        model = cfg.get("model")
        models = backend.get("models")
        if model and isinstance(models, list) and models:
            if any(model in m for m in models if m):
                add(OK, "model", f"'{model}' available")
            else:
                have = ", ".join(m for m in models if m) or "none"
                add(WARN, "model", f"'{model}' not pulled — try `ollama pull {model}` (have: {have})")

        # Embeddings readiness — reuses data already fetched (no extra I/O).
        embeddings = cfg.get("embeddings")
        if embeddings == "ollama":
            embed_model = cfg.get("embed_model")
            if isinstance(models, list) and models and embed_model:
                if any(embed_model in m for m in models if m):
                    add(OK, "embeddings", f"ollama embeddings '{embed_model}' available")
                else:
                    add(WARN, "embeddings",
                        f"embedding model '{embed_model}' not pulled — try `ollama pull {embed_model}`")
            else:
                add(INFO, "embeddings", f"ollama embeddings ('{embed_model}') — model list unavailable")
        elif embeddings:
            add(OK, "embeddings", f"{embeddings} embeddings (offline, no model to pull)")

        docs = (health.get("index") or {}).get("documents", 0)
        add(INFO if docs else WARN, "index",
            f"{docs} documents indexed" + ("" if docs else " — add some with `aios index <path>`"))

        add(OK if p["sessions_status"] == 200 else WARN, "storage",
            "session store reachable" if p["sessions_status"] == 200 else "cannot read sessions")

        tools = p["tools"] or {}
        if tools.get("enabled"):
            add(OK, "tools", f"{len(tools.get('tools', []))} tools enabled")
        else:
            add(INFO, "tools", "tools disabled")

        if cfg:
            add(INFO if cfg.get("audit_enabled") else WARN, "audit",
                "audit log enabled" if cfg.get("audit_enabled") else "audit log disabled")
            add(INFO, "auth",
                "bearer token set" if cfg.get("token_set") else "no auth token (loopback only)")

    cfg = p.get("config") or {}
    if cfg.get("backend") == "ollama" and not p["ollama_bin"]:
        add(WARN, "ollama", "ollama not found on PATH — install from https://ollama.com")
    elif p["ollama_bin"]:
        add(OK, "ollama", f"ollama at {p['ollama_bin']}")

    home_bin = p["home_bin"]
    if home_bin in p["path"].split(os.pathsep):
        add(OK, "path", f"{home_bin} on PATH")
    else:
        add(WARN, "path", f"{home_bin} not on PATH — add: export PATH=\"$HOME/.local/bin:$PATH\"")

    return checks


def render(checks, out) -> int:
    tty = hasattr(out, "isatty") and out.isatty()
    counts = {OK: 0, WARN: 0, FAIL: 0, INFO: 0}
    out.write("AIOS doctor\n\n")
    for c in checks:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
        symbol, color = _SYMBOLS.get(c["status"], ("·", "0"))
        if tty and color != "0":
            symbol = f"\033[{color}m{symbol}\033[0m"
        out.write(f"  {symbol} {c['name']}: {c['message']}\n")
    out.write(f"\n{counts[OK]} ok · {counts[WARN]} warning(s) · {counts[FAIL]} failed\n")
    return 1 if counts[FAIL] else 0


def run(base_url, env, out) -> int:
    return render(evaluate(gather(base_url, env)), out)


def main() -> int:
    port = os.environ.get("AIOS_PORT", "8765")
    base_url = os.environ.get("AIOS_URL", f"http://127.0.0.1:{port}")
    return run(base_url, dict(os.environ), sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
