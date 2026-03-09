"""Public ``query()`` async generator function.

Provider-agnostic: pass ``options.provider`` to route to a different backend.
Defaults to ``claude-code`` when no provider is specified.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

from ._internal.query import Query
from ._internal.transport import Transport
from ._internal.transport.subprocess_cli import SubprocessCLITransport
from .types import ClaudeAgentOptions, Message


async def query(
    *,
    prompt: str | AsyncIterable[dict[str, Any]],
    options: ClaudeAgentOptions | None = None,
    transport: Transport | None = None,
) -> AsyncIterator[Message]:
    """Create a new session and iterate over messages from Claude Code.

    Each call starts a fresh session. For continuing conversations, use
    :class:`ClaudeSDKClient` instead.

    Supports multi-provider routing via ``options.provider``:

    - ``"claude-code"`` (default) — delegates to Claude Code CLI
    - ``"anthropic"`` — Anthropic API directly
    - ``"openai"`` — OpenAI API
    - ``"openrouter"`` — OpenRouter (OpenAI-compatible)
    - ``"codex"`` — OpenAI Codex
    - ``"copilot"`` — GitHub Copilot
    - ``"kimi-cli"`` — Kimi
    - Any registered custom provider name

    Usage::

        async for message in query(prompt="What is 2+2?"):
            print(message)

        # With a different provider:
        opts = ClaudeAgentOptions(provider="anthropic", model="claude-sonnet-4-20250514")
        async for message in query(prompt="Hello", options=opts):
            print(message)
    """
    opts = options or ClaudeAgentOptions()
    provider = getattr(opts, "provider", None) or "claude-code"

    if provider == "claude-code":
        # Default path: use subprocess CLI transport
        yield_from = _query_claude_code(prompt, opts, transport)
        async for msg in yield_from:
            yield msg
    else:
        # Non-Claude provider: route through multi-provider system
        if not isinstance(prompt, str):
            raise ValueError(
                "AsyncIterable prompt is only supported with the claude-code provider"
            )

        async for msg in _query_other_provider(prompt, opts, provider):
            yield msg


async def _query_claude_code(
    prompt: str | AsyncIterable[dict[str, Any]],
    opts: ClaudeAgentOptions,
    transport: Transport | None,
) -> AsyncIterator[Message]:
    """Original claude-code query path."""
    t = transport or SubprocessCLITransport(opts)
    own_transport = transport is None

    try:
        await t.connect()
        q = Query(t, opts)
        async for msg in q.run(prompt):
            yield msg
    finally:
        if own_transport:
            await t.close()


async def _query_other_provider(
    prompt: str,
    opts: ClaudeAgentOptions,
    provider: str,
) -> AsyncIterator[Message]:
    """Route to a non-Claude provider and adapt the stream to SDK messages."""
    from .adapt_stream import adapt_stream
    from .providers import create_provider
    from .types_core import AgentDef, RunConfig, ToolDef

    # Extract tools from mock MCP servers (if any)
    tools: list[ToolDef] = []
    mcp_servers = opts.mcp_servers
    if isinstance(mcp_servers, dict):
        from .mcp_server import extract_tools_from_mcp_servers
        tools = extract_tools_from_mcp_servers(mcp_servers)

    agent = AgentDef(
        name="default",
        description="Default agent",
        prompt=opts.system_prompt if isinstance(opts.system_prompt, str) else "You are a helpful assistant.",
        model=opts.model,
        tools=tools if tools else None,
    )

    config = RunConfig(
        provider=provider,
        agent=agent,
        max_turns=opts.max_turns,
        work_dir=str(opts.cwd) if opts.cwd else None,
        provider_options=dict(opts.extra_args) if opts.extra_args else None,
    )

    backend = await create_provider(config)
    try:
        from ._internal.message_parser import parse_message

        async for sdk_msg in adapt_stream(backend.run(prompt, config)):
            yield parse_message(sdk_msg)
    finally:
        await backend.close()
