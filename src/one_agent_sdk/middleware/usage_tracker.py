"""Usage tracker middleware — accumulates token usage stats."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from ..types_core import DoneChunk, Middleware, MiddlewareContext, StreamChunk
from .core import define_middleware


@dataclass
class UsageStats:
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0


@dataclass
class UsageTrackerOptions:
    """Options for the usage tracker middleware."""

    on_usage: object | None = None  # Callable[[UsageStats], None]


@dataclass
class UsageTrackerHandle:
    """Handle returned by ``usage_tracker()``."""

    middleware: Middleware
    _stats: UsageStats = field(default_factory=UsageStats)

    def get_stats(self) -> UsageStats:
        return UsageStats(
            input_tokens=self._stats.input_tokens,
            output_tokens=self._stats.output_tokens,
            requests=self._stats.requests,
        )

    def reset(self) -> None:
        self._stats.input_tokens = 0
        self._stats.output_tokens = 0
        self._stats.requests = 0


def usage_tracker(options: UsageTrackerOptions | None = None) -> UsageTrackerHandle:
    """Create a usage tracker middleware."""
    opts = options or UsageTrackerOptions()
    stats = UsageStats()

    async def _middleware(
        stream: AsyncGenerator[StreamChunk, None], context: MiddlewareContext
    ) -> AsyncGenerator[StreamChunk, None]:
        async for chunk in stream:
            if isinstance(chunk, DoneChunk) and chunk.usage:
                stats.input_tokens += chunk.usage.input_tokens
                stats.output_tokens += chunk.usage.output_tokens
                stats.requests += 1
                if callable(opts.on_usage):
                    opts.on_usage(UsageStats(
                        input_tokens=stats.input_tokens,
                        output_tokens=stats.output_tokens,
                        requests=stats.requests,
                    ))
            yield chunk

    mw = define_middleware(_middleware)
    return UsageTrackerHandle(middleware=mw, _stats=stats)
