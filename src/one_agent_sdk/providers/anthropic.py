"""Anthropic API provider — uses the @anthropic-ai/sdk Python package."""

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
        tools.append({"name": t.name, "description": t.description, "input_schema": schema})

    for name in agent.handoffs or []:
        target = agents.get(name) if agents else None
        desc = f"Hand off to {target.name}: {target.description}" if target else f"Hand off to {name}"
        tools.append({
            "name": handoff_tool_name(name),
            "description": desc,
            "input_schema": {"type": "object", "properties": {}},
        })
    return tools


class _AnthropicProvider:
    def __init__(self, config: RunConfig, client: Any) -> None:
        self._config = config
        self._client = client
        self._active_agent = config.agent
        self._tool_map = build_tool_map(self._active_agent)
        self._tools = _build_tools(self._active_agent, config.agents)
        self._messages: list[dict[str, Any]] = []
        self._max_tokens = int((config.provider_options or {}).get("maxTokens", 8192))

    def _swap_agent(self, agent: AgentDef) -> None:
        self._active_agent = agent
        self._tool_map = build_tool_map(agent)
        self._tools = _build_tools(agent, self._config.agents)

    async def _run_stream(self) -> AsyncGenerator[StreamChunk, None]:
        max_turns = self._config.max_turns or 100

        for _turn in range(max_turns):
            model = self._active_agent.model or "claude-sonnet-4-20250514"

            create_kwargs: dict[str, Any] = {
                "model": model,
                "system": self._active_agent.prompt,
                "messages": self._messages,
                "max_tokens": self._max_tokens,
                "stream": True,
            }
            if self._tools:
                create_kwargs["tools"] = self._tools

            stream = await self._client.messages.create(**create_kwargs)

            full_text = ""
            content_blocks: list[dict[str, Any]] = []
            current_tool_use: dict[str, Any] | None = None
            stop_reason: str | None = None
            usage: UsageInfo | None = None

            async for event in stream:
                event_type = getattr(event, "type", "")

                if event_type == "message_start":
                    msg = getattr(event, "message", None)
                    if msg and hasattr(msg, "usage"):
                        u = msg.usage
                        usage = UsageInfo(
                            input_tokens=getattr(u, "input_tokens", 0),
                            output_tokens=getattr(u, "output_tokens", 0),
                        )

                elif event_type == "content_block_start":
                    cb = getattr(event, "content_block", None)
                    if cb and getattr(cb, "type", "") == "tool_use":
                        current_tool_use = {
                            "id": getattr(cb, "id", ""),
                            "name": getattr(cb, "name", ""),
                            "json_input": "",
                        }

                elif event_type == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta:
                        delta_type = getattr(delta, "type", "")
                        if delta_type == "text_delta":
                            text = getattr(delta, "text", "")
                            full_text += text
                            yield TextChunk(text=text)
                        elif delta_type == "input_json_delta" and current_tool_use is not None:
                            current_tool_use["json_input"] += getattr(delta, "partial_json", "")

                elif event_type == "content_block_stop":
                    if current_tool_use:
                        input_data = {}
                        if current_tool_use["json_input"]:
                            input_data = json.loads(current_tool_use["json_input"])
                        content_blocks.append({
                            "type": "tool_use",
                            "id": current_tool_use["id"],
                            "name": current_tool_use["name"],
                            "input": input_data,
                        })
                        current_tool_use = None
                    else:
                        content_blocks.append({"type": "text", "text": full_text})

                elif event_type == "message_delta":
                    delta = getattr(event, "delta", None)
                    if delta and hasattr(delta, "stop_reason"):
                        stop_reason = delta.stop_reason
                    u2 = getattr(event, "usage", None)
                    if u2:
                        usage = UsageInfo(
                            input_tokens=(usage.input_tokens if usage else 0) + getattr(u2, "input_tokens", 0),
                            output_tokens=(usage.output_tokens if usage else 0) + getattr(u2, "output_tokens", 0),
                        )

            # Add assistant message
            self._messages.append({
                "role": "assistant",
                "content": content_blocks if content_blocks else full_text,
            })

            if stop_reason != "tool_use":
                yield DoneChunk(text=full_text, usage=usage)
                return

            # Process tool calls
            tool_use_blocks = [b for b in content_blocks if b.get("type") == "tool_use"]
            tool_results: list[dict[str, Any]] = []

            for block in tool_use_blocks:
                yield ToolCallChunk(
                    tool_name=block["name"],
                    tool_args=block["input"],
                    tool_call_id=block["id"],
                )

                handoff_target = parse_handoff(block["name"])
                if handoff_target:
                    target_agent = (self._config.agents or {}).get(handoff_target)
                    if not target_agent:
                        yield ErrorChunk(error=f"Unknown handoff target: {handoff_target}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block["id"],
                            "content": f'Error: unknown agent "{handoff_target}"',
                        })
                        continue

                    yield HandoffChunk(from_agent=self._active_agent.name, to_agent=handoff_target)
                    self._swap_agent(target_agent)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": f"Handed off to {handoff_target}",
                    })
                    continue

                tool = self._tool_map.get(block["name"])
                if not tool:
                    error_result = f'Error: unknown tool "{block["name"]}"'
                    yield ToolResultChunk(tool_call_id=block["id"], result=error_result)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": error_result,
                    })
                    continue

                try:
                    result = await tool.handler(block["input"])
                    yield ToolResultChunk(tool_call_id=block["id"], result=result)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": result,
                    })
                except Exception as exc:
                    error_result = f"Error: {exc}"
                    yield ToolResultChunk(tool_call_id=block["id"], result=error_result)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": error_result,
                    })

            self._messages.append({"role": "user", "content": tool_results})

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


async def create_anthropic_provider(config: RunConfig) -> ProviderBackend:
    """Create an Anthropic API provider backend."""
    try:
        import anthropic
    except ImportError as exc:
        raise ImportError("Anthropic provider requires 'anthropic' package: pip install anthropic") from exc

    opts = config.provider_options or {}
    api_key = opts.get("apiKey") or os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.AsyncAnthropic(api_key=api_key)
    return _AnthropicProvider(config, client)  # type: ignore[return-value]
