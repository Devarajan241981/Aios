"""Assistant orchestration.

Combines the AIOS system persona, live device context, optional conversation
history, and the user's prompt into a message list, then delegates to a backend.
This is the single seam where future capabilities (semantic retrieval, tool use,
automation) will be composed.
"""

from __future__ import annotations

from .context import gather_context, render_context
from .retriever import Retriever

SYSTEM_PROMPT = (
    "You are AIOS, the built-in assistant of a privacy-first, local AI operating "
    "system. You run entirely on the user's device; no data leaves the machine. "
    "Be concise, practical, and action-oriented. When the user asks to do "
    "something on their computer, give the concrete steps or commands. Prefer "
    "plain language over jargon.\n\n"
    "Current device context (for grounding; only mention it if relevant):\n{context}"
)


RAG_PREAMBLE = (
    "Relevant excerpts from the user's own indexed files. Use them if helpful and "
    "cite the file path in brackets; if they are not relevant, ignore them.\n\n"
)


class Assistant:
    def __init__(self, backend, config, context_provider=gather_context, retriever=None):
        self.backend = backend
        self.config = config
        self.context_provider = context_provider
        self.retriever = retriever

    def build_messages(self, prompt: str, history=None):
        context = render_context(self.context_provider())
        messages = [{"role": "system", "content": SYSTEM_PROMPT.format(context=context)}]

        if self.retriever is not None:
            hits = self.retriever.retrieve(prompt)
            if hits:
                messages.append(
                    {"role": "system", "content": RAG_PREAMBLE + Retriever.render(hits)}
                )

        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        return messages

    def ask(self, prompt: str, history=None) -> str:
        messages = self.build_messages(prompt, history)
        return self.backend.chat(
            messages, model=self.config.model, timeout=self.config.request_timeout
        )

    def ask_stream(self, prompt: str, history=None):
        """Yield reply text deltas. Retrieval/build happen on first iteration."""
        messages = self.build_messages(prompt, history)
        yield from self.backend.stream_chat(
            messages, model=self.config.model, timeout=self.config.request_timeout
        )
