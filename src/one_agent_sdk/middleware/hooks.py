"""Hooks middleware — per-type callbacks for stream chunks."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass

from ..types_core import (
    DoneChunk,
    ErrorChunk,
    HandoffChunk,
    Middleware,
    MiddlewareContext,
    StreamChunk,
    TextChunk,
    ToolCallChunk,
    ToolResultChunk,
)
from .core import define_middleware


@dataclass
class HooksOptions:
    on_text: Callable[[TextChunk], None] | None = None
    on_tool_call: Callable[[ToolCallChunk], None] | None = None
    on_tool_result: Callable[[ToolResultChunk], None] | None = None
    on_handoff: Callable[[HandoffChunk], None] | None = None
    on_error: Callable[[ErrorChunk], None] | None = None
    on_done: Callable[[DoneChunk], None] | None = None
    on_chunk: Callable[[StreamChunk], None] | None = None


def hooks(options: HooksOptions) -> Middleware:
    """Create a hooks middleware with per-type callbacks."""

    async def _middleware(
        stream: AsyncGenerator[StreamChunk, None], context: MiddlewareContext
    ) -> AsyncGenerator[StreamChunk, None]:
        async for chunk in stream:
            if options.on_chunk:
                options.on_chunk(chunk)

            if isinstance(chunk, TextChunk) and options.on_text:
                options.on_text(chunk)
            elif isinstance(chunk, ToolCallChunk) and options.on_tool_call:
                options.on_tool_call(chunk)
            elif isinstance(chunk, ToolResultChunk) and options.on_tool_result:
                options.on_tool_result(chunk)
            elif isinstance(chunk, HandoffChunk) and options.on_handoff:
                options.on_handoff(chunk)
            elif isinstance(chunk, ErrorChunk) and options.on_error:
                options.on_error(chunk)
            elif isinstance(chunk, DoneChunk) and options.on_done:
                options.on_done(chunk)

            yield chunk

    return define_middleware(_middleware)
