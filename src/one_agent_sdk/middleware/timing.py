"""Timing middleware — measures time to first chunk, first text, and total duration."""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass

from ..types_core import Middleware, MiddlewareContext, StreamChunk, TextChunk
from .core import define_middleware


@dataclass
class TimingInfo:
    time_to_first_chunk: float = 0.0
    time_to_first_text: float | None = None
    duration: float = 0.0


@dataclass
class TimingOptions:
    on_first_text: Callable[[float], None] | None = None
    on_complete: Callable[[TimingInfo], None] | None = None


@dataclass
class TimingHandle:
    middleware: Middleware
    _info: TimingInfo | None = None

    def get_info(self) -> TimingInfo | None:
        return TimingInfo(
            time_to_first_chunk=self._info.time_to_first_chunk,
            time_to_first_text=self._info.time_to_first_text,
            duration=self._info.duration,
        ) if self._info else None


def timing(options: TimingOptions | None = None) -> TimingHandle:
    """Create a timing middleware."""
    opts = options or TimingOptions()
    handle = TimingHandle(middleware=lambda s, c: s)  # placeholder

    async def _middleware(
        stream: AsyncGenerator[StreamChunk, None], context: MiddlewareContext
    ) -> AsyncGenerator[StreamChunk, None]:
        start = time.perf_counter()
        time_to_first_chunk: float | None = None
        time_to_first_text: float | None = None

        async for chunk in stream:
            now = time.perf_counter()

            if time_to_first_chunk is None:
                time_to_first_chunk = (now - start) * 1000

            if time_to_first_text is None and isinstance(chunk, TextChunk):
                time_to_first_text = (now - start) * 1000
                if opts.on_first_text:
                    opts.on_first_text(time_to_first_text)

            yield chunk

        duration = (time.perf_counter() - start) * 1000
        info = TimingInfo(
            time_to_first_chunk=time_to_first_chunk or 0,
            time_to_first_text=time_to_first_text,
            duration=duration,
        )
        handle._info = info
        if opts.on_complete:
            opts.on_complete(info)

    handle.middleware = define_middleware(_middleware)
    return handle
