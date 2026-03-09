"""OpenRouter provider — wraps the OpenAI-compatible provider with OpenRouter base URL."""

from __future__ import annotations

import os
from typing import Any

from ..types_core import ProviderBackend, RunConfig


async def create_openrouter_provider(config: RunConfig) -> ProviderBackend:
    """Create an OpenRouter provider backend."""
    from .openai import create_openai_compatible_provider

    opts: dict[str, Any] = config.provider_options or {}
    api_key = opts.get("apiKey") or os.environ.get("OPENROUTER_API_KEY")

    if not api_key:
        raise ValueError(
            "OpenRouter requires an API key. "
            "Set OPENROUTER_API_KEY or pass provider_options={'apiKey': '...'}"
        )

    if not config.agent.model:
        raise ValueError(
            "OpenRouter requires agent.model to be set "
            "(e.g. 'anthropic/claude-sonnet-4')"
        )

    default_headers: dict[str, str] = {}
    if opts.get("httpReferer"):
        default_headers["HTTP-Referer"] = str(opts["httpReferer"])
    if opts.get("xTitle"):
        default_headers["X-Title"] = str(opts["xTitle"])

    return await create_openai_compatible_provider(
        config,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers=default_headers or None,
    )
