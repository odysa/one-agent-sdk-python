"""OpenAI Codex provider — uses the @openai/codex-sdk."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any

from ..types_core import (
    DoneChunk,
    ErrorChunk,
    ProviderBackend,
    RunConfig,
    StreamChunk,
    TextChunk,
    ToolCallChunk,
    ToolResultChunk,
    UsageInfo,
)


async def create_codex_provider(config: RunConfig) -> ProviderBackend:
    """Create a Codex provider backend.

    Requires the ``codex-sdk`` package.
    """
    try:
        from codex_sdk import Codex
    except ImportError as exc:
        raise ImportError(
            "Codex provider requires 'codex-sdk' package: pip install codex-sdk"
        ) from exc

    opts = config.provider_options or {}
    codex = Codex(api_key=opts.get("apiKey"), **(opts.get("codexOptions") or {}))

    thread = codex.start_thread(
        model=config.agent.model,
        working_directory=config.work_dir or os.getcwd(),
        approval_policy="never",
        **(opts.get("threadOptions") or {}),
    )

    system_prefix = f"[System: {config.agent.prompt}]\n\n" if config.agent.prompt else ""

    class _CodexProvider:
        async def _run_prompt(self, prompt: str) -> AsyncGenerator[StreamChunk, None]:
            result = await thread.run_streamed(f"{system_prefix}{prompt}")
            full_text = ""

            async for event in result.events:
                if event.type == "item.completed":
                    item = event.item
                    if item.type == "agent_message":
                        full_text += item.text
                        yield TextChunk(text=item.text)
                    elif item.type == "mcp_tool_call":
                        yield ToolCallChunk(
                            tool_name=f"{item.server}__{item.tool}",
                            tool_args=item.arguments or {},
                            tool_call_id=item.id,
                        )
                        result_text = ""
                        if item.result:
                            result_text = "".join(
                                c.text for c in item.result.content if hasattr(c, "text")
                            )
                        else:
                            result_text = getattr(item.error, "message", "") if item.error else ""
                        yield ToolResultChunk(tool_call_id=item.id, result=result_text)
                    elif item.type == "command_execution":
                        yield ToolCallChunk(
                            tool_name="command_execution",
                            tool_args={"command": item.command},
                            tool_call_id=item.id,
                        )
                        yield ToolResultChunk(tool_call_id=item.id, result=item.aggregated_output)
                    elif item.type == "file_change":
                        yield ToolCallChunk(
                            tool_name="file_change",
                            tool_args={"changes": item.changes},
                            tool_call_id=item.id,
                        )
                        yield ToolResultChunk(tool_call_id=item.id, result=item.status)
                    elif item.type == "error":
                        yield ErrorChunk(error=item.message)
                        yield DoneChunk(text=full_text)
                        return

                elif event.type == "turn.completed":
                    yield DoneChunk(
                        text=full_text,
                        usage=UsageInfo(
                            input_tokens=event.usage.input_tokens,
                            output_tokens=event.usage.output_tokens,
                        ),
                    )
                    return
                elif event.type == "turn.failed":
                    yield ErrorChunk(error=event.error.message)
                    yield DoneChunk(text=full_text)
                    return

            yield DoneChunk(text=full_text)

        def run(self, prompt: str, cfg: RunConfig) -> AsyncGenerator[StreamChunk, None]:
            return self._run_prompt(prompt)

        def chat(self, message: str) -> AsyncGenerator[StreamChunk, None]:
            return self._run_prompt(message)

        async def close(self) -> None:
            pass

    return _CodexProvider()  # type: ignore[return-value]
