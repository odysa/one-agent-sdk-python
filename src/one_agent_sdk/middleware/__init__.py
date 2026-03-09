"""Middleware system for the One Agent SDK.

Middleware transforms the stream between provider and consumer.
"""

from .core import apply_middleware, define_middleware
from .filter import FilterOptions, filter
from .guardrails import GuardrailsOptions, guardrails
from .hooks import HooksOptions, hooks
from .logging import LoggingOptions, logging
from .text_collector import TextCollectorHandle, TextCollectorOptions, text_collector
from .timing import TimingHandle, TimingInfo, TimingOptions, timing
from .usage_tracker import UsageStats, UsageTrackerHandle, UsageTrackerOptions, usage_tracker

__all__ = [
    # Core
    "apply_middleware",
    "define_middleware",
    # Built-in middleware
    "filter",
    "FilterOptions",
    "guardrails",
    "GuardrailsOptions",
    "hooks",
    "HooksOptions",
    "logging",
    "LoggingOptions",
    "text_collector",
    "TextCollectorHandle",
    "TextCollectorOptions",
    "timing",
    "TimingHandle",
    "TimingInfo",
    "TimingOptions",
    "usage_tracker",
    "UsageStats",
    "UsageTrackerHandle",
    "UsageTrackerOptions",
]
