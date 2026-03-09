"""Claude Code provider — delegates to @anthropic-ai/claude-agent-sdk via our SDK compat layer."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from ..types_core import (
    AgentDef,
    DoneChunk,
    ProviderBackend,
    RunConfig,
    StreamChunk,
    TextChunk,
    ToolCallChunk,
    ToolDef,
    ToolResultChunk,
)


class _ClaudeProvider:
    def __init__(self, config: RunConfig, query_fn: Any, tool_fn: Any, create_mcp_fn: Any) -> None:
        self._config = config
        self._query = query_fn
        self._tool = tool_fn
        self._create_mcp = create_mcp_fn
        self._session_id: str | None = None

    async def _run_query(self, prompt: str) -> AsyncGenerator[StreamChunk, None]:
        agent = self._config.agent
        agent_tools = agent.tools or []

        # Build in-process MCP server for user-defined tools
        mcp_server: Any = None
        tool_names: list[str] = []

        if agent_tools:
            server_name = agent.name
            mcp_server = self._create_mcp(
                name=server_name,
                version="1.0.0",
                tools=[
                    self._tool(
                        t.name,
                        t.description,
                        t.parameters or {},
                        handler=lambda args, _extra=None, _t=t: _wrap_handler(_t, args),
                    )
                    for t in agent_tools
                ],
            )
            tool_names = [f"mcp__{server_name}__{t.name}" for t in agent_tools]

        # Merge MCP servers
        mcp_servers: dict[str, Any] = {}
        if mcp_server:
            mcp_servers[agent.name] = mcp_server
        if agent.mcp_servers:
            mcp_servers.update(agent.mcp_servers)
        if self._config.mcp_servers:
            mcp_servers.update(self._config.mcp_servers)

        # Build agent definitions for handoffs
        agents: list[dict[str, Any]] | None = None
        if agent.handoffs and self._config.agents:
            agents_map = self._config.agents
            agents = []
            for name in agent.handoffs:
                a = agents_map.get(name)
                if a:
                    agents.append({
                        "name": a.name,
                        "description": a.description,
                        "instructions": a.prompt,
                        "tools": [t.name for t in (a.tools or [])],
                    })

        import os

        env = {**os.environ}
        env.pop("CLAUDECODE", None)

        options: dict[str, Any] = {
            "systemPrompt": agent.prompt,
            "permissionMode": "bypassPermissions",
            "allowDangerouslySkipPermissions": True,
            "env": env,
        }

        if agent.model:
            options["model"] = agent.model
        if mcp_servers:
            options["mcpServers"] = mcp_servers
        if tool_names:
            options["allowedTools"] = tool_names
        if agents:
            options["agents"] = agents
        if self._session_id:
            options["resume"] = self._session_id
        if self._config.max_turns:
            options["maxTurns"] = self._config.max_turns
        if self._config.provider_options:
            options.update(self._config.provider_options)

        full_text = ""

        async for msg in self._query(prompt=prompt, options=options):
            if msg.get("type") == "system" and msg.get("subtype") == "init":
                self._session_id = msg.get("session_id")

            if msg.get("type") == "assistant":
                message = msg.get("message", {})
                for block in message.get("content", []):
                    if isinstance(block, dict):
                        if block.get("type") == "text" and block.get("text"):
                            full_text += block["text"]
                            yield TextChunk(text=block["text"])
                        elif block.get("type") == "tool_use":
                            yield ToolCallChunk(
                                tool_name=block.get("name", ""),
                                tool_args=block.get("input", {}),
                                tool_call_id=block.get("id", ""),
                            )
                    elif hasattr(block, "text") and hasattr(block, "type"):
                        if getattr(block, "type", None) == "text":
                            text = getattr(block, "text", "")
                            if text:
                                full_text += text
                                yield TextChunk(text=text)

            if msg.get("type") == "result":
                yield ToolResultChunk(
                    tool_call_id=msg.get("tool_use_id", ""),
                    result=str(msg.get("content", "")),
                )

        yield DoneChunk(text=full_text)

    def run(self, prompt: str, config: RunConfig) -> AsyncGenerator[StreamChunk, None]:
        return self._run_query(prompt)

    def chat(self, message: str) -> AsyncGenerator[StreamChunk, None]:
        return self._run_query(message)

    async def close(self) -> None:
        pass


async def _wrap_handler(t: ToolDef, args: Any) -> dict[str, Any]:
    result = await t.handler(args)
    return {"content": [{"type": "text", "text": result}]}


async def create_claude_provider(config: RunConfig) -> ProviderBackend:
    """Create a Claude Code provider backend."""
    # Import our own SDK compat layer
    from .. import create_sdk_mcp_server, query, tool

    # Wrap query to be usable as an async iterable
    async def query_fn(prompt: str, options: dict[str, Any]) -> Any:
        from ..types import ClaudeAgentOptions

        opts = ClaudeAgentOptions()
        for key, value in options.items():
            if hasattr(opts, key):
                setattr(opts, key, value)

        async for msg in query(prompt=prompt, options=opts):
            # Convert typed message to dict for the provider
            yield _message_to_dict(msg)

    return _ClaudeProvider(config, query_fn, tool, create_sdk_mcp_server)  # type: ignore[return-value]


def _message_to_dict(msg: Any) -> dict[str, Any]:
    """Convert a typed message to a plain dict."""
    if hasattr(msg, "__dataclass_fields__"):
        from dataclasses import asdict

        result = asdict(msg)
        result["type"] = type(msg).__name__.lower().replace("message", "")
        return result
    return {"type": "unknown"}
