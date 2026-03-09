"""Guardrails middleware — content filtering."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field

from ..types_core import ErrorChunk, Middleware, MiddlewareContext, StreamChunk, TextChunk
from .core import define_middleware


@dataclass
class GuardrailsOptions:
    blocked_keywords: list[str] = field(default_factory=list)
    validate: Callable[[str], bool | str] | None = None
    on_block: str = "error"  # "error" or "drop"
    case_insensitive: bool = True


def guardrails(options: GuardrailsOptions) -> Middleware:
    """Create a guardrails middleware for content filtering."""
    normalized_keywords = (
        [k.lower() for k in options.blocked_keywords]
        if options.case_insensitive
        else list(options.blocked_keywords)
    )

    async def _middleware(
        stream: AsyncGenerator[StreamChunk, None], context: MiddlewareContext
    ) -> AsyncGenerator[StreamChunk, None]:
        async for chunk in stream:
            if not isinstance(chunk, TextChunk):
                yield chunk
                continue

            text_to_check = chunk.text.lower() if options.case_insensitive else chunk.text
            blocked = any(kw in text_to_check for kw in normalized_keywords)

            if blocked:
                if options.on_block == "error":
                    yield ErrorChunk(error="Content blocked by guardrails")
                continue

            if options.validate:
                result = options.validate(chunk.text)
                if result is False:
                    if options.on_block == "error":
                        yield ErrorChunk(error="Content blocked by guardrails")
                    continue
                if isinstance(result, str):
                    yield TextChunk(text=result)
                    continue

            yield chunk

    return define_middleware(_middleware)
