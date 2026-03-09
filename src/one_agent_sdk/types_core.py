"""Core types for the multi-provider agent framework.

These types power the provider-agnostic streaming interface, middleware,
sessions, and multi-agent handoffs. They are the Python equivalent of
``src/types.ts`` in the TypeScript SDK.
"""

from __future__ import annotations

import abc
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# StreamChunk — discriminated union for streaming output
# ---------------------------------------------------------------------------


@dataclass
class TextChunk:
    type: str = field(default="text", init=False)
    text: str = ""


@dataclass
class ToolCallChunk:
    type: str = field(default="tool_call", init=False)
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_call_id: str = ""


@dataclass
class ToolResultChunk:
    type: str = field(default="tool_result", init=False)
    tool_call_id: str = ""
    result: str = ""


@dataclass
class HandoffChunk:
    type: str = field(default="handoff", init=False)
    from_agent: str = ""
    to_agent: str = ""


@dataclass
class ErrorChunk:
    type: str = field(default="error", init=False)
    error: str = ""


@dataclass
class DoneChunk:
    type: str = field(default="done", init=False)
    text: str | None = None
    usage: UsageInfo | None = None


@dataclass
class UsageInfo:
    input_tokens: int = 0
    output_tokens: int = 0


StreamChunk = TextChunk | ToolCallChunk | ToolResultChunk | HandoffChunk | ErrorChunk | DoneChunk

# ---------------------------------------------------------------------------
# McpServerConfig (simple config for agents, not the full SDK config)
# ---------------------------------------------------------------------------


@dataclass
class AgentMcpServerConfig:
    """MCP server configuration for use within agent definitions."""

    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None


# ---------------------------------------------------------------------------
# ToolDef — tool definition with handler
# ---------------------------------------------------------------------------


@dataclass
class ToolDef:
    """Tool definition with parameter schema and async handler."""

    name: str = ""
    description: str = ""
    parameters: Any = None  # Pydantic model, dict, or JSON Schema
    handler: Callable[..., Awaitable[str]] = field(default=None)  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# AgentDef — agent definition
# ---------------------------------------------------------------------------


@dataclass
class AgentDef:
    """Agent definition with optional tools and handoffs."""

    name: str = ""
    description: str = ""
    prompt: str = ""
    tools: list[ToolDef] | None = None
    handoffs: list[str] | None = None
    model: str | None = None
    mcp_servers: dict[str, AgentMcpServerConfig] | None = None


# ---------------------------------------------------------------------------
# Provider types
# ---------------------------------------------------------------------------

BuiltinProvider = str  # "claude-code" | "codex" | "copilot" | "kimi-cli" | "openai" | "anthropic" | "openrouter"
Provider = str  # BuiltinProvider or registered custom name

BUILTIN_PROVIDERS = frozenset(
    {"claude-code", "codex", "copilot", "kimi-cli", "openai", "anthropic", "openrouter"}
)


# ---------------------------------------------------------------------------
# Middleware types
# ---------------------------------------------------------------------------


@dataclass
class MiddlewareContext:
    """Context passed to each middleware function."""

    agent: AgentDef = field(default_factory=AgentDef)
    provider: str = ""


Middleware = Callable[
    [AsyncGenerator[StreamChunk, None], MiddlewareContext],
    AsyncGenerator[StreamChunk, None],
]

# ---------------------------------------------------------------------------
# RunConfig — configuration for a run
# ---------------------------------------------------------------------------


@dataclass
class RunConfig:
    """Configuration for a run."""

    provider: str = "claude-code"
    agent: AgentDef = field(default_factory=AgentDef)
    agents: dict[str, AgentDef] | None = None
    mcp_servers: dict[str, AgentMcpServerConfig] | None = None
    provider_options: dict[str, Any] | None = None
    work_dir: str | None = None
    max_turns: int | None = None
    signal: Any | None = None  # asyncio-compatible abort signal
    middleware: list[Middleware] | None = None
    response_schema: Any | None = None  # Pydantic model or JSON Schema for validation


# ---------------------------------------------------------------------------
# AgentRun — handle returned by run()
# ---------------------------------------------------------------------------


@dataclass
class AgentRun:
    """Handle returned by ``run()``.  Provides stream, chat, and close."""

    stream: AsyncGenerator[StreamChunk, None]
    chat: Callable[[str], AsyncGenerator[StreamChunk, None]]
    close: Callable[[], Awaitable[None]]


# ---------------------------------------------------------------------------
# ProviderBackend — abstract base for all provider implementations
# ---------------------------------------------------------------------------


@runtime_checkable
class ProviderBackend(Protocol):
    """Provider backend interface — all backends implement this."""

    def run(self, prompt: str, config: RunConfig) -> AsyncGenerator[StreamChunk, None]: ...
    def chat(self, message: str) -> AsyncGenerator[StreamChunk, None]: ...
    async def close(self) -> None: ...
