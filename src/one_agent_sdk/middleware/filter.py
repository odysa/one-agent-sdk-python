"""Filter middleware — include/exclude stream chunk types."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field

from ..types_core import Middleware, MiddlewareContext, StreamChunk
from .core import define_middleware


@dataclass
class FilterOptions:
    exclude: list[str] | None = None
    include: list[str] | None = None
    predicate: Callable[[StreamChunk], bool] | None = None


def filter(options: FilterOptions) -> Middleware:
    """Create a filter middleware."""
    if options.predicate:
        check = options.predicate
    elif options.include:
        include_set = set(options.include)
        check = lambda c: c.type in include_set
    elif options.exclude:
        exclude_set = set(options.exclude)
        check = lambda c: c.type not in exclude_set
    else:
        check = lambda _c: True

    async def _middleware(
        stream: AsyncGenerator[StreamChunk, None], context: MiddlewareContext
    ) -> AsyncGenerator[StreamChunk, None]:
        async for chunk in stream:
            if check(chunk):
                yield chunk

    return define_middleware(_middleware)
