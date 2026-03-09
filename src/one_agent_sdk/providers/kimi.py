"""Kimi provider — uses @moonshot-ai/kimi-agent-sdk."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from ..types_core import (
    DoneChunk,
    HandoffChunk,
    ProviderBackend,
    RunConfig,
    StreamChunk,
    TextChunk,
    ToolCallChunk,
    ToolResultChunk,
)
from ..utils.handoff import handoff_tool_name, parse_handoff


async def create_kimi_provider(config: RunConfig) -> ProviderBackend:
    """Create a Kimi provider backend.

    Requires the ``kimi-agent-sdk`` package.
    """
    try:
        from kimi_agent_sdk import create_external_tool, create_session
    except ImportError as exc:
        raise ImportError(
            "Kimi provider requires 'kimi-agent-sdk' package: pip install kimi-agent-sdk"
        ) from exc

    agent_tools = config.agent.tools or []

    external_tools = [
        create_external_tool(
            name=t.name,
            description=t.description,
            parameters=t.parameters,
            handler=lambda params, _t=t: _kimi_handler(_t, params),
        )
        for t in agent_tools
    ]

    current_agent = config.agent

    for target_name in config.agent.handoffs or []:
        target_agent = (config.agents or {}).get(target_name)
        external_tools.append(
            create_external_tool(
                name=handoff_tool_name(target_name),
                description=target_agent.description if target_agent else f"Transfer to {target_name}",
                parameters={},
                handler=lambda: {"output": f"Transferred to {target_name}", "message": "ok"},
            )
        )

    import os

    session = create_session(
        workDir=config.work_dir or os.getcwd(),
        model=config.agent.model or "kimi-latest",
        externalTools=external_tools,
    )

    class _KimiProvider:
        async def _run_prompt(self, prompt: str) -> AsyncGenerator[StreamChunk, None]:
            nonlocal current_agent
            turn = session.prompt(prompt)
            full_text = ""

            async for event in turn:
                if event.type == "ContentPart" and event.payload.type == "text":
                    full_text += event.payload.text
                    yield TextChunk(text=event.payload.text)

                if event.type == "ApprovalRequest":
                    await turn.approve(event.payload.id, "approve")

                if event.type == "ToolCall":
                    name = event.payload.name
                    yield ToolCallChunk(
                        tool_name=name,
                        tool_args=getattr(event.payload, "arguments", {}) or {},
                        tool_call_id=getattr(event.payload, "id", ""),
                    )
                    handoff_target = parse_handoff(name)
                    if handoff_target:
                        target = (config.agents or {}).get(handoff_target)
                        if target:
                            yield HandoffChunk(from_agent=current_agent.name, to_agent=handoff_target)
                            current_agent = target

                if event.type == "ToolResult":
                    output = getattr(event.payload, "output", "")
                    yield ToolResultChunk(
                        tool_call_id=getattr(event.payload, "id", ""),
                        result=output if isinstance(output, str) else str(output),
                    )

            yield DoneChunk(text=full_text)

        def run(self, prompt: str, cfg: RunConfig) -> AsyncGenerator[StreamChunk, None]:
            return self._run_prompt(prompt)

        def chat(self, message: str) -> AsyncGenerator[StreamChunk, None]:
            return self._run_prompt(message)

        async def close(self) -> None:
            await session.close()

    return _KimiProvider()  # type: ignore[return-value]


async def _kimi_handler(t: Any, params: Any) -> dict[str, str]:
    result = await t.handler(params)
    return {"output": result, "message": "ok"}
