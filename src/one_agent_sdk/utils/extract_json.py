"""Extract JSON from text that may contain markdown code fences."""

from __future__ import annotations

import re

_FENCE_RE = re.compile(r"```(?:json)?\s*\n([\s\S]*?)\n```")


def extract_json(text: str) -> str:
    """Extract a JSON string from text that may contain markdown code fences.

    Handles raw JSON strings, ``json ... `` fences, and plain `` ... `` fences.
    """
    trimmed = text.strip()
    match = _FENCE_RE.search(trimmed)
    if match:
        return match.group(1).strip()
    return trimmed
