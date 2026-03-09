"""Provider backends for the One Agent SDK."""

from __future__ import annotations

from ..types_core import ProviderBackend, RunConfig


async def create_provider(config: RunConfig) -> ProviderBackend:
    """Resolve a provider backend from registry or built-in providers."""
    from ..registry import get_provider

    # Check registry first (custom providers)
    factory = get_provider(config.provider)
    if factory is not None:
        return await factory(config)

    # Built-in providers (lazy imports)
    match config.provider:
        case "claude-code":
            from .claude import create_claude_provider

            return await create_claude_provider(config)
        case "anthropic":
            from .anthropic import create_anthropic_provider

            return await create_anthropic_provider(config)
        case "openai":
            from .openai import create_openai_provider

            return await create_openai_provider(config)
        case "openrouter":
            from .openrouter import create_openrouter_provider

            return await create_openrouter_provider(config)
        case "kimi-cli":
            from .kimi import create_kimi_provider

            return await create_kimi_provider(config)
        case "codex":
            from .codex import create_codex_provider

            return await create_codex_provider(config)
        case "copilot":
            from .copilot import create_copilot_provider

            return await create_copilot_provider(config)
        case _:
            raise ValueError(
                f"Unknown provider: {config.provider}. "
                "Use: claude-code, codex, copilot, kimi-cli, openai, anthropic, "
                "openrouter, or register a custom provider with register_provider()"
            )


__all__ = ["ProviderBackend", "create_provider"]
