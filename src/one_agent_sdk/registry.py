"""Provider registry for custom provider backends."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from .types_core import ProviderBackend, RunConfig

ProviderFactory = Callable[[RunConfig], Awaitable[ProviderBackend]]

_registry: dict[str, ProviderFactory] = {}


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Register a custom provider."""
    _registry[name] = factory


def get_provider(name: str) -> ProviderFactory | None:
    """Get a registered provider factory (returns ``None`` if not found)."""
    return _registry.get(name)


def clear_providers() -> None:
    """Clear all registered providers (useful for testing)."""
    _registry.clear()
