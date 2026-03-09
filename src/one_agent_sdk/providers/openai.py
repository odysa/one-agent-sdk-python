"""OpenAI API provider — uses the openai Python package."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator
from typing import Any

from ..types_core import (
    AgentDef,
    DoneChunk,
    ErrorChunk,
    HandoffChunk,
    ProviderBackend,
    RunConfig,
    StreamChunk,
    TextChunk,
    ToolCallChunk,
    ToolResultChunk,
    UsageInfo,
)
from ..utils.handoff import handoff_tool_name, parse_handoff
from ..utils.tool_map import build_tool_map


def _build_tools(agent: AgentDef, agents: dict[str, AgentDef] | None = None) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for t in agent.tools or []:
        schema = t.parameters
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        tools.append({
            "type": "function",
            "function": {"name": t.name, "description": t.description, "parameters": schema},
        })

    for name in agent.handoffs or []:
        target = agents.get(name) if agents else None
        desc = f"Hand off to {target.name}: {target.description}" if target else f"Hand off to {name}"
        tools.append({
            "type": "function",
            "function": {
                "name": handoff_tool_name(name),
                "description": desc,
                "parameters": {"type": "object", "properties": {}},
            },
        })
    return tools


class _OpenAICompatibleProvider:
    def __init__(self, config: RunConfig, client: Any) -> None:
        self._config = config
        self._client = client
        self._active_agent = config.agent
        self._tool_map = build_tool_map(self._active_agent)
        self._tools = _build_tools(self._active_agent, config.agents)
        self._messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._active_agent.prompt},
        ]

    def _swap_agent(self, agent: AgentDef) -> None:
        self._active_agent = agent
        self._tool_map = build_tool_map(agent)
        self._tools = _build_tools(agent, self._config.agents)
        self._messages[0] = {"role": "system", "content": agent.prompt}

    async def _run_stream(self) -> AsyncGenerator[StreamChunk, None]:
        max_turns = self._config.max_turns or 100

        for _turn in range(max_turns):
            model = self._active_agent.model or "gpt-4o"

            create_kwargs: dict[str, Any] = {
                "model": model,
                "messages": self._messages,
                "stream": True,
            }
            if self._tools:
                create_kwargs["tools"] = self._tools

            stream = await self._client.chat.completions.create(**create_kwargs)

            full_text = ""
            tool_calls: dict[int, dict[str, str]] = {}
            finish_reason: str | None = None
            usage: UsageInfo | None = None

            async for chunk in stream:
                choices = getattr(chunk, "choices", [])
                if not choices:
                    continue
                choice = choices[0]
                delta = getattr(choice, "delta", None)

                if delta and getattr(delta, "content", None):
                    full_text += delta.content
                    yield TextChunk(text=delta.content)

                if delta and getattr(delta, "tool_calls", None):
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls:
                            tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                        entry = tool_calls[idx]
                        if tc.id:
                            entry["id"] = tc.id
                        if tc.function and tc.function.name:
                            entry["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            entry["arguments"] += tc.function.arguments

                if getattr(choice, "finish_reason", None):
                    finish_reason = choice.finish_reason

                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage:
                    usage = UsageInfo(
                        input_tokens=getattr(chunk_usage, "prompt_tokens", 0),
                        output_tokens=getattr(chunk_usage, "completion_tokens", 0),
                    )

            # Build assistant message
            assistant_msg: dict[str, Any] = {"role": "assistant"}
            if full_text:
                assistant_msg["content"] = full_text
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for tc in tool_calls.values()
                ]
            self._messages.append(assistant_msg)

            if finish_reason != "tool_calls" or not tool_calls:
                yield DoneChunk(text=full_text, usage=usage)
                return

            # Process tool calls
            for tc in tool_calls.values():
                args: dict[str, Any] = {}
                try:
                    args = json.loads(tc["arguments"] or "{}")
                except json.JSONDecodeError:
                    yield ErrorChunk(error=f"Failed to parse tool arguments for {tc['name']}")

                yield ToolCallChunk(tool_name=tc["name"], tool_args=args, tool_call_id=tc["id"])

                handoff_target = parse_handoff(tc["name"])
                if handoff_target:
                    target_agent = (self._config.agents or {}).get(handoff_target)
                    if not target_agent:
                        yield ErrorChunk(error=f"Unknown handoff target: {handoff_target}")
                        self._messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": f'Error: unknown agent "{handoff_target}"',
                        })
                        continue

                    yield HandoffChunk(from_agent=self._active_agent.name, to_agent=handoff_target)
                    self._swap_agent(target_agent)
                    self._messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": f"Handed off to {handoff_target}",
                    })
                    continue

                tool = self._tool_map.get(tc["name"])
                if not tool:
                    error_result = f'Error: unknown tool "{tc["name"]}"'
                    yield ToolResultChunk(tool_call_id=tc["id"], result=error_result)
                    self._messages.append({"role": "tool", "tool_call_id": tc["id"], "content": error_result})
                    continue

                try:
                    result = await tool.handler(args)
                    yield ToolResultChunk(tool_call_id=tc["id"], result=result)
                    self._messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                except Exception as exc:
                    error_result = f"Error: {exc}"
                    yield ToolResultChunk(tool_call_id=tc["id"], result=error_result)
                    self._messages.append({"role": "tool", "tool_call_id": tc["id"], "content": error_result})

        yield ErrorChunk(error=f"Max turns ({self._config.max_turns or 100}) exceeded")
        yield DoneChunk()

    def run(self, prompt: str, config: RunConfig) -> AsyncGenerator[StreamChunk, None]:
        self._messages.append({"role": "user", "content": prompt})
        return self._run_stream()

    def chat(self, message: str) -> AsyncGenerator[StreamChunk, None]:
        self._messages.append({"role": "user", "content": message})
        return self._run_stream()

    async def close(self) -> None:
        pass


async def create_openai_compatible_provider(
    config: RunConfig,
    *,
    api_key: str,
    base_url: str | None = None,
    default_headers: dict[str, str] | None = None,
) -> ProviderBackend:
    """Create an OpenAI-compatible provider backend."""
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise ImportError("OpenAI provider requires 'openai' package: pip install openai") from exc

    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    if default_headers:
        kwargs["default_headers"] = default_headers

    client = AsyncOpenAI(**kwargs)
    return _OpenAICompatibleProvider(config, client)  # type: ignore[return-value]


async def create_openai_provider(config: RunConfig) -> ProviderBackend:
    """Create an OpenAI API provider backend."""
    opts = config.provider_options or {}
    api_key = opts.get("apiKey") or os.environ.get("OPENAI_API_KEY", "")
    return await create_openai_compatible_provider(config, api_key=api_key)
