"""Adapt a StreamChunk async generator to emit SDKMessage-shaped dicts.

This bridges the multi-provider streaming interface to the
@anthropic-ai/claude-agent-sdk output format used by ``query()``.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

from .types_core import (
    DoneChunk,
    ErrorChunk,
    HandoffChunk,
    StreamChunk,
    TextChunk,
    ToolCallChunk,
    ToolResultChunk,
)


async def adapt_stream(
    stream: AsyncGenerator[StreamChunk, None],
) -> AsyncGenerator[dict[str, Any], None]:
    """Convert ``StreamChunk`` to SDK message dicts."""
    session_id = str(uuid.uuid4())

    yield {"type": "system", "subtype": "init", "session_id": session_id}

    async for chunk in stream:
        if isinstance(chunk, TextChunk):
            yield {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": chunk.text}]},
            }
        elif isinstance(chunk, ToolCallChunk):
            yield {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": chunk.tool_call_id,
                            "name": chunk.tool_name,
                            "input": chunk.tool_args,
                        }
                    ]
                },
            }
        elif isinstance(chunk, ToolResultChunk):
            yield {
                "type": "result",
                "tool_use_id": chunk.tool_call_id,
                "content": chunk.result,
            }
        elif isinstance(chunk, HandoffChunk):
            yield {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": f"[Handoff: {chunk.from_agent} → {chunk.to_agent}]"}
                    ]
                },
            }
        elif isinstance(chunk, ErrorChunk):
            yield {
                "type": "result",
                "subtype": "error_during_execution",
                "error": chunk.error,
            }
        elif isinstance(chunk, DoneChunk):
            yield {
                "type": "result",
                "subtype": "success",
                "text": chunk.text,
                "usage": {
                    "inputTokens": chunk.usage.input_tokens,
                    "outputTokens": chunk.usage.output_tokens,
                } if chunk.usage else None,
            }
