"""Tool framework: capabilities the assistant can invoke to act on the machine.

Design principles (see docs/decisions/0002-tools-safety.md):

* **Least privilege.** Filesystem tools are sandboxed to the user's home plus
  any explicitly configured roots; symlink escapes are rejected via realpath.
* **Safe by default, gated when not.** Every tool declares ``safe`` (read-only /
  side-effect-free). Safe tools run automatically. Non-safe (mutating) tools are
  never executed without explicit approval — the registry returns a
  ``needs_approval`` result instead. We ship only safe tools; the gate exists so
  future mutating tools cannot be run silently.
* **Never crash the daemon.** Tool errors are captured and returned as data.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Callable

from .context import gather_context

# Commands run_command may execute unless overridden via AIOS_ALLOWED_COMMANDS.
# Intentionally a small, low-risk set; command execution is gated by approval
# regardless of what is on this list.
DEFAULT_ALLOWED_COMMANDS = {
    "ls", "cat", "pwd", "date", "whoami", "df", "du", "uptime",
    "echo", "head", "tail", "wc", "uname", "hostname",
}


class ToolError(Exception):
    """Recoverable, user-facing tool failure (bad args, denied path, ...)."""


@dataclass
class ToolContext:
    config: object
    retriever: object | None = None
    context_provider: Callable = gather_context


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict           # JSON Schema for the arguments object
    func: Callable             # (args: dict, ctx: ToolContext) -> str
    safe: bool = True          # read-only / no side effects
    preview: Callable | None = None  # (args, ctx) -> human description of the effect


def signature(name: str, args: dict) -> str:
    """Stable content hash of a tool call, used for content-addressed approval."""
    blob = json.dumps({"name": name, "args": args or {}}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


# --- sandbox helpers -----------------------------------------------------

def _allowed_roots(config):
    roots = [os.path.realpath(os.path.expanduser("~"))]
    for extra in getattr(config, "allowed_roots", ()) or ():
        roots.append(os.path.realpath(os.path.expanduser(extra)))
    return roots


def _resolve_within(path: str, config) -> str:
    if not path:
        raise ToolError("a path is required")
    real = os.path.realpath(os.path.expanduser(path))
    for root in _allowed_roots(config):
        if real == root or real.startswith(root + os.sep):
            return real
    raise ToolError(f"path not allowed: {path} (outside permitted roots)")


# --- built-in safe tools -------------------------------------------------

def _current_time(args, ctx):
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _system_info(args, ctx):
    info = ctx.context_provider()
    return "\n".join(f"{k}: {v}" for k, v in info.items())


def _list_dir(args, ctx):
    real = _resolve_within(args.get("path") or "~", ctx.config)
    if not os.path.isdir(real):
        raise ToolError(f"not a directory: {args.get('path')}")
    try:
        entries = sorted(os.listdir(real))
    except OSError as exc:
        raise ToolError(f"cannot list directory: {exc}") from exc
    lines = []
    for name in entries[:200]:
        marker = "/" if os.path.isdir(os.path.join(real, name)) else ""
        lines.append(name + marker)
    suffix = "" if len(entries) <= 200 else f"\n… ({len(entries) - 200} more)"
    return ("\n".join(lines) + suffix) if lines else "(empty)"


def _read_file(args, ctx):
    real = _resolve_within(args.get("path"), ctx.config)
    if not os.path.isfile(real):
        raise ToolError(f"not a file: {args.get('path')}")
    if os.path.getsize(real) > 5_000_000:
        raise ToolError("file too large to read (>5 MB)")
    max_bytes = int(args.get("max_bytes", 20000))
    with open(real, "r", encoding="utf-8", errors="ignore") as fh:
        return fh.read(max_bytes)


def _search_notes(args, ctx):
    if ctx.retriever is None:
        raise ToolError("semantic index is not available")
    query = (args.get("query") or "").strip()
    if not query:
        raise ToolError("search_notes requires a 'query'")
    hits = ctx.retriever.retrieve(query)
    if not hits:
        return "no matches in the indexed files"
    return "\n\n".join(f"[{h['source']}]\n{h['text']}" for h in hits)


# --- built-in MUTATING tools (require approval) --------------------------

def _write_file(args, ctx):
    content = args.get("content", "")
    real = _resolve_within(args.get("path"), ctx.config)
    parent = os.path.dirname(real)
    if parent and not os.path.isdir(parent):
        raise ToolError(f"parent directory does not exist: {parent}")
    try:
        with open(real, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError as exc:
        raise ToolError(f"could not write file: {exc}") from exc
    return f"wrote {len(content)} bytes to {real}"


def _write_file_preview(args, ctx):
    try:
        real = _resolve_within(args.get("path"), ctx.config)
    except ToolError as exc:
        return f"WOULD BE REJECTED: {exc}"
    content = args.get("content", "")
    verb = "Overwrite" if os.path.exists(real) else "Create"
    body = content if len(content) <= 500 else content[:500] + f"\n… (+{len(content) - 500} more bytes)"
    return f"{verb} {real} ({len(content)} bytes):\n{body}"


def _allowed_commands(config):
    extra = set(getattr(config, "allowed_commands", ()) or ())
    return DEFAULT_ALLOWED_COMMANDS | extra


def _run_command(args, ctx):
    command = (args.get("command") or "").strip()
    if not command:
        raise ToolError("run_command requires a 'command'")
    parts = shlex.split(command)
    if not parts:
        raise ToolError("empty command")
    binary = os.path.basename(parts[0])
    allowed = _allowed_commands(ctx.config)
    if binary not in allowed:
        raise ToolError(
            f"command not allowed: {binary!r} "
            f"(allowed: {', '.join(sorted(allowed))}; extend with AIOS_ALLOWED_COMMANDS)"
        )
    try:
        proc = subprocess.run(
            parts, capture_output=True, text=True, timeout=10,
            cwd=os.path.expanduser("~"),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ToolError(f"command failed: {exc}") from exc
    out = proc.stdout
    if proc.stderr:
        out += f"\n[stderr]\n{proc.stderr}"
    if proc.returncode != 0:
        out += f"\n[exit {proc.returncode}]"
    return out[:20000] or "(no output)"


def _run_command_preview(args, ctx):
    return f"Run shell command (no shell metacharacters, 10s timeout):\n    {args.get('command', '')}"


# --- registry ------------------------------------------------------------

class Registry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str):
        return self._tools.get(name)

    def names(self):
        return sorted(self._tools)

    def describe(self):
        return [
            {"name": t.name, "description": t.description, "safe": t.safe}
            for t in self._tools.values()
        ]

    def schemas(self):
        """OpenAI/Ollama-compatible tool schema list."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def preview(self, name: str, args: dict, ctx: ToolContext) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"unknown tool: {name}"
        if tool.preview is not None:
            try:
                return tool.preview(args or {}, ctx)
            except Exception as exc:  # a preview must never raise
                return f"{name}({args}) [preview unavailable: {exc}]"
        return f"{name}({args})"

    def execute(self, name: str, args: dict, ctx: ToolContext, approve: bool = False) -> dict:
        tool = self._tools.get(name)
        if tool is None:
            return {"ok": False, "error": f"unknown tool: {name}"}
        if not tool.safe and not approve:
            return {
                "ok": False,
                "needs_approval": True,
                "error": f"tool '{name}' is mutating and requires explicit approval",
            }
        try:
            return {"ok": True, "result": tool.func(args or {}, ctx)}
        except ToolError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # a buggy tool must not take down the daemon
            return {"ok": False, "error": f"tool error: {exc}"}


_STRING = {"type": "string"}


def default_registry() -> Registry:
    reg = Registry()
    reg.register(Tool(
        "current_time", "Get the current local date and time.",
        {"type": "object", "properties": {}}, _current_time,
    ))
    reg.register(Tool(
        "system_info", "Get basic device info (host, OS, user, battery).",
        {"type": "object", "properties": {}}, _system_info,
    ))
    reg.register(Tool(
        "list_dir", "List the contents of a directory the user can access.",
        {"type": "object", "properties": {"path": _STRING}, "required": ["path"]},
        _list_dir,
    ))
    reg.register(Tool(
        "read_file", "Read the text contents of a file the user can access.",
        {"type": "object",
         "properties": {"path": _STRING, "max_bytes": {"type": "integer"}},
         "required": ["path"]},
        _read_file,
    ))
    reg.register(Tool(
        "search_notes", "Semantically search the user's indexed files.",
        {"type": "object", "properties": {"query": _STRING}, "required": ["query"]},
        _search_notes,
    ))
    # --- mutating tools: safe=False, so they require preview + approval ---
    reg.register(Tool(
        "write_file",
        "Write text to a file the user can access (creates or overwrites).",
        {"type": "object",
         "properties": {"path": _STRING, "content": _STRING},
         "required": ["path", "content"]},
        _write_file, safe=False, preview=_write_file_preview,
    ))
    reg.register(Tool(
        "run_command",
        "Run an allowlisted, non-interactive shell command and return its output.",
        {"type": "object", "properties": {"command": _STRING}, "required": ["command"]},
        _run_command, safe=False, preview=_run_command_preview,
    ))
    return reg
