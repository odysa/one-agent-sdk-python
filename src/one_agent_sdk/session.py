"""Session management for multi-turn conversations."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from .types_core import AgentRun, DoneChunk, RunConfig, StreamChunk, TextChunk


# ---------------------------------------------------------------------------
# Message & SessionStore
# ---------------------------------------------------------------------------


@dataclass
class SessionMessage:
    """A message in the conversation history."""

    role: str  # "user" | "assistant"
    content: str = ""


class SessionStore(Protocol):
    """Interface for session storage backends."""

    async def load(self, session_id: str) -> list[SessionMessage]: ...
    async def save(self, session_id: str, messages: list[SessionMessage]) -> None: ...


class MemoryStore:
    """In-memory session store."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[SessionMessage]] = {}

    async def load(self, session_id: str) -> list[SessionMessage]:
        return list(self._sessions.get(session_id, []))

    async def save(self, session_id: str, messages: list[SessionMessage]) -> None:
        self._sessions[session_id] = list(messages)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@dataclass
class SessionConfig:
    """Configuration for creating a session."""

    session_id: str | None = None
    store: SessionStore | None = None
    runner: Callable[[str, RunConfig], Awaitable[AgentRun]] | None = None


class Session:
    """Multi-turn conversation session with history management."""

    def __init__(self, config: SessionConfig | None = None) -> None:
        cfg = config or SessionConfig()
        self._id = cfg.session_id or str(uuid.uuid4())
        self._store: SessionStore = cfg.store or MemoryStore()
        self._runner = cfg.runner

    @property
    def id(self) -> str:
        return self._id

    async def run(self, prompt: str, config: RunConfig) -> AgentRun:
        """Run a prompt with conversation history prepended."""
        from .runner import run as default_run

        runner = self._runner or default_run
        history = await self._store.load(self._id)

        history_context = "\n\n".join(
            f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}"
            for m in history
        )

        full_prompt = (
            f"Previous conversation:\n{history_context}\n\nUser: {prompt}"
            if history_context
            else prompt
        )

        history.append(SessionMessage(role="user", content=prompt))
        await self._store.save(self._id, history)

        agent_run = await runner(full_prompt, config)

        return AgentRun(
            stream=_wrap_stream_with_history(agent_run.stream, history, self._store, self._id),
            chat=lambda message: self._chat(message, agent_run, history),
            close=agent_run.close,
        )

    def _chat(
        self,
        message: str,
        agent_run: AgentRun,
        history: list[SessionMessage],
    ) -> AsyncGenerator[StreamChunk, None]:
        history.append(SessionMessage(role="user", content=message))
        return _wrap_stream_with_history(agent_run.chat(message), history, self._store, self._id)

    async def get_history(self) -> list[SessionMessage]:
        """Get conversation history."""
        return await self._store.load(self._id)

    async def clear(self) -> None:
        """Clear conversation history."""
        await self._store.save(self._id, [])


async def _wrap_stream_with_history(
    stream: AsyncGenerator[StreamChunk, None],
    history: list[SessionMessage],
    store: SessionStore,
    session_id: str,
) -> AsyncGenerator[StreamChunk, None]:
    assistant_text = ""

    async for chunk in stream:
        if isinstance(chunk, TextChunk):
            assistant_text += chunk.text
        if isinstance(chunk, DoneChunk):
            text = chunk.text if chunk.text is not None else assistant_text
            history.append(SessionMessage(role="assistant", content=text))
            await store.save(session_id, history)
        yield chunk


def create_session(config: SessionConfig | None = None) -> Session:
    """Create a session for multi-turn conversations."""
    return Session(config)
