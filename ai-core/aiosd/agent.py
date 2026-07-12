"""Agent loop: let the model call tools, then answer.

Backend-agnostic. It speaks one normalized message shape and lets each backend
translate to its wire format:

    {"role": "system"|"user"|"assistant"|"tool", "content": str,
     "tool_calls"?: [{"id", "name", "arguments": dict}],   # assistant turns
     "tool_call_id"?: str, "name"?: str}                    # tool result turns

Each ``chat_with_tools`` call returns ``{"content": str|None, "tool_calls": [...]}``.
Backends without tool support simply return the plain answer and no tool calls,
so the loop degrades gracefully to a single-shot reply.
"""

from __future__ import annotations

import json

from .audit import summarize_args
from .tools import signature


class Agent:
    """Tool-using loop with a preview-before-run gate.

    Safe tools run automatically. When the model requests a *mutating* tool that
    has not been approved, the loop halts before executing anything in that turn
    and returns the pending action(s) with previews and content-addressed
    ``signature`` values. The caller approves specific signatures and re-runs;
    only calls whose signature was approved (or all, if ``approve_all``) execute.
    This keeps the flow stateless over HTTP while guaranteeing the user only ever
    runs exactly what they previewed.
    """

    def __init__(self, backend, registry, ctx, config, max_steps: int = 5, audit=None):
        self.backend = backend
        self.registry = registry
        self.ctx = ctx
        self.config = config
        self.max_steps = max_steps
        self.audit = audit

    def _record(self, event):
        if self.audit is not None:
            self.audit.record(event)

    def _approved(self, name, args, approved, approve_all):
        return approve_all or signature(name, args) in approved

    def run(self, messages, approved=None, approve_all: bool = False) -> dict:
        approved = set(approved or ())
        conversation = list(messages)
        steps = []
        content = ""

        for _ in range(self.max_steps):
            resp = self.backend.chat_with_tools(
                conversation,
                self.registry.schemas(),
                model=self.config.model,
                timeout=self.config.request_timeout,
            )
            content = resp.get("content") or ""
            tool_calls = resp.get("tool_calls") or []
            if not tool_calls:
                return {"status": "complete", "reply": content, "steps": steps}

            # Halt before executing anything if the turn contains an unapproved
            # mutation — surface previews for the caller to approve.
            pending = []
            for call in tool_calls:
                tool = self.registry.get(call.get("name"))
                args = call.get("arguments") or {}
                if tool is not None and not tool.safe and not self._approved(
                    call.get("name"), args, approved, approve_all
                ):
                    pending.append({
                        "tool": call.get("name"),
                        "args": args,
                        "preview": self.registry.preview(call.get("name"), args, self.ctx),
                        "signature": signature(call.get("name"), args),
                    })
            if pending:
                for p in pending:
                    self._record({"event": "pending", "tool": p["tool"],
                                  "signature": p["signature"],
                                  "args": summarize_args(p["args"])})
                return {"status": "needs_approval", "pending": pending, "steps": steps}

            conversation.append(
                {"role": "assistant", "content": content, "tool_calls": tool_calls}
            )
            for call in tool_calls:
                name = call.get("name")
                args = call.get("arguments") or {}
                approve = self._approved(name, args, approved, approve_all)
                result = self.registry.execute(name, args, self.ctx, approve=approve)
                steps.append({"tool": name, "args": args, "result": result})
                tool = self.registry.get(name)
                self._record({"event": "tool", "tool": name,
                              "safe": (tool.safe if tool else None),
                              "approved": approve, "ok": result.get("ok"),
                              "error": result.get("error"),
                              "args": summarize_args(args)})
                conversation.append({
                    "role": "tool",
                    "tool_call_id": call.get("id") or name,
                    "name": name,
                    "content": json.dumps(result),
                })

        return {
            "status": "complete",
            "reply": content or "(stopped after reaching the tool-step limit)",
            "steps": steps,
        }
