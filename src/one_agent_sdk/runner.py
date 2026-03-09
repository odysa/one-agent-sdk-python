"""Runner — run/run_to_completion (deprecated, use query() instead).

These functions provide the legacy API for running agents.
"""

from __future__ import annotations

import json
import warnings
from typing import Any

from .middleware.core import apply_middleware
from .providers import create_provider
from .types_core import AgentRun, MiddlewareContext, RunConfig, StreamChunk, TextChunk
from .utils.extract_json import extract_json


async def run(prompt: str, config: RunConfig) -> AgentRun:
    """Start a run — returns a stream, chat handle, and close function.

    .. deprecated::
        Will be removed in v0.2. Use ``query()`` instead.
    """
    warnings.warn("run() is deprecated, use query() instead", DeprecationWarning, stacklevel=2)

    provider = await create_provider(config)
    middleware = config.middleware

    if not middleware:
        return AgentRun(
            stream=provider.run(prompt, config),
            chat=lambda message: provider.chat(message),
            close=provider.close,
        )

    mw_context = MiddlewareContext(agent=config.agent, provider=config.provider)

    return AgentRun(
        stream=apply_middleware(provider.run(prompt, config), middleware, mw_context),
        chat=lambda message: apply_middleware(provider.chat(message), middleware, mw_context),
        close=provider.close,
    )


async def run_to_completion(prompt: str, config: RunConfig) -> str | Any:
    """Run to completion and return collected text.

    If ``config.response_schema`` is set, parses and validates the response.

    .. deprecated::
        Will be removed in v0.2. Use ``query()`` instead.
    """
    warnings.warn("run_to_completion() is deprecated, use query() instead", DeprecationWarning, stacklevel=2)

    agent_run = await run(prompt, config)
    text = ""

    async for chunk in agent_run.stream:
        if isinstance(chunk, TextChunk):
            text += chunk.text

    await agent_run.close()

    if not config.response_schema:
        return text

    json_text = extract_json(text)
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse response as JSON: {json_text}")

    # Support Pydantic models
    schema = config.response_schema
    if hasattr(schema, "model_validate"):
        return schema.model_validate(parsed)
    if hasattr(schema, "parse_obj"):
        return schema.parse_obj(parsed)

    return parsed
