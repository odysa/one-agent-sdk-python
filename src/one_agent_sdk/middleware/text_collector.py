"""Text collector middleware — accumulates text output."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass

from ..types_core import DoneChunk, Middleware, MiddlewareContext, StreamChunk, TextChunk
from .core import define_middleware


@dataclass
class TextCollectorOptions:
    on_text: Callable[[str], None] | None = None
    on_complete: Callable[[str], None] | None = None
    prefer_done_text: bool = True


@dataclass
class TextCollectorHandle:
    middleware: Middleware
    _text: str = ""

    def get_text(self) -> str:
        return self._text


def text_collector(options: TextCollectorOptions | None = None) -> TextCollectorHandle:
    """Create a text collector middleware."""
    opts = options or TextCollectorOptions()
    handle = TextCollectorHandle(middleware=lambda s, c: s)  # placeholder

    async def _middleware(
        stream: AsyncGenerator[StreamChunk, None], context: MiddlewareContext
    ) -> AsyncGenerator[StreamChunk, None]:
        handle._text = ""

        async for chunk in stream:
            if isinstance(chunk, TextChunk):
                handle._text += chunk.text
                if opts.on_text:
                    opts.on_text(handle._text)

            if isinstance(chunk, DoneChunk) and opts.prefer_done_text and chunk.text is not None:
                handle._text = chunk.text

            yield chunk

        if opts.on_complete:
            opts.on_complete(handle._text)

    handle.middleware = define_middleware(_middleware)
    return handle
