"""Handoff naming conventions for multi-agent transfer tools."""

from __future__ import annotations

_HANDOFF_PREFIX = "transfer_to_"


def handoff_tool_name(agent_name: str) -> str:
    """Return the synthetic tool name for handing off to *agent_name*."""
    return f"{_HANDOFF_PREFIX}{agent_name}"


def parse_handoff(tool_name: str) -> str | None:
    """If *tool_name* is a handoff tool, return the target agent name."""
    if tool_name.startswith(_HANDOFF_PREFIX):
        return tool_name[len(_HANDOFF_PREFIX) :]
    return None
