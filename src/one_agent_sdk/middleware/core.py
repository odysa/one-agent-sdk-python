"""Core middleware primitives."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from ..types_core import Middleware, MiddlewareContext, StreamChunk


def define_middleware(fn: Middleware) -> Middleware:
    """Identity helper for defining middleware (for symmetry with the TS SDK)."""
    return fn


def apply_middleware(
    stream: AsyncGenerator[StreamChunk, None],
    middleware: list[Middleware],
    context: MiddlewareContext,
) -> AsyncGenerator[StreamChunk, None]:
    """Compose middleware left-to-right around a stream."""
    result = stream
    for mw in middleware:
        result = mw(result, context)
    return result
