"""Delegates for v2 unstable session APIs.

These require the Claude Code CLI and delegate to the internal client.
"""

from __future__ import annotations

from typing import Any


async def unstable_v2_create_session(options: dict[str, Any]) -> Any:
    """Create a new multi-turn session (v2 API, unstable).

    This creates a persistent session that supports multiple prompts
    via the Claude Code CLI subprocess.
    """
    from .client import InternalClient
    from ..types import ClaudeAgentOptions

    opts = ClaudeAgentOptions()
    if "model" in options:
        opts.model = options["model"]
    if "permissionMode" in options:
        opts.permission_mode = options["permissionMode"]
    if "allowedTools" in options:
        opts.allowed_tools = options["allowedTools"]
    if "disallowedTools" in options:
        opts.disallowed_tools = options["disallowedTools"]
    if "pathToClaudeCodeExecutable" in options:
        opts.cli_path = options["pathToClaudeCodeExecutable"]
    if "hooks" in options:
        opts.hooks = options["hooks"]
    if "canUseTool" in options:
        opts.can_use_tool = options["canUseTool"]
    if "env" in options:
        opts.env = {k: v for k, v in options["env"].items() if v is not None}

    client = InternalClient(opts)
    await client.connect()

    class _V2Session:
        def __init__(self) -> None:
            self._client = client
            self._session_id: str | None = None

        @property
        def session_id(self) -> str | None:
            return self._session_id

        async def send(self, message: str | dict[str, Any]) -> None:
            prompt = message if isinstance(message, str) else message.get("content", "")
            await self._client.send_query(prompt)

        async def stream(self):
            async for msg in self._client.receive_messages():
                yield msg

        def close(self) -> None:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._client.disconnect())
                else:
                    loop.run_until_complete(self._client.disconnect())
            except RuntimeError:
                pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc: object) -> None:
            await self._client.disconnect()

    return _V2Session()


async def unstable_v2_prompt(message: str, options: dict[str, Any]) -> Any:
    """One-shot prompt (v2 API, unstable).

    Creates a session, sends a single message, collects the result, and closes.
    """
    from ..types import ResultMessage

    session = await unstable_v2_create_session(options)
    try:
        await session.send(message)
        result = None
        async for msg in session.stream():
            if isinstance(msg, ResultMessage):
                result = msg
                break
        return result
    finally:
        session.close()


async def unstable_v2_resume_session(session_id: str, options: dict[str, Any]) -> Any:
    """Resume an existing session (v2 API, unstable)."""
    opts_with_resume = {**options, "resume": session_id}

    from .client import InternalClient
    from ..types import ClaudeAgentOptions

    agent_opts = ClaudeAgentOptions()
    agent_opts.resume = session_id
    if "model" in options:
        agent_opts.model = options["model"]
    if "permissionMode" in options:
        agent_opts.permission_mode = options["permissionMode"]
    if "pathToClaudeCodeExecutable" in options:
        agent_opts.cli_path = options["pathToClaudeCodeExecutable"]

    client = InternalClient(agent_opts)
    await client.connect()

    class _V2ResumedSession:
        def __init__(self) -> None:
            self._client = client
            self._session_id = session_id

        @property
        def session_id(self) -> str:
            return self._session_id

        async def send(self, message: str | dict) -> None:
            prompt = message if isinstance(message, str) else message.get("content", "")
            await self._client.send_query(prompt)

        async def stream(self):
            async for msg in self._client.receive_messages():
                yield msg

        def close(self) -> None:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._client.disconnect())
                else:
                    loop.run_until_complete(self._client.disconnect())
            except RuntimeError:
                pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc: object) -> None:
            await self._client.disconnect()

    return _V2ResumedSession()
