"""Logging middleware — logs stream chunks."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from typing import Any

from ..types_core import Middleware, MiddlewareContext, StreamChunk
from .core import define_middleware


@dataclass
class LoggingOptions:
    """Options for the logging middleware."""

    logger: Callable[[str, StreamChunk], None] | None = None
    types: list[str] | None = None
    label: str = "[middleware:logging]"


def logging(options: LoggingOptions | None = None) -> Middleware:
    """Create a logging middleware that logs stream chunks."""
    opts = options or LoggingOptions()
    log = opts.logger or (lambda message, _chunk: print(message))
    type_set = set(opts.types) if opts.types else None
    label = opts.label

    async def _middleware(
        stream: AsyncGenerator[StreamChunk, None], context: MiddlewareContext
    ) -> AsyncGenerator[StreamChunk, None]:
        async for chunk in stream:
            if type_set is None or chunk.type in type_set:
                log(f"{label} {chunk.type}: {chunk}", chunk)
            yield chunk

    return define_middleware(_middleware)
