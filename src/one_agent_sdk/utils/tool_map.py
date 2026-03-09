"""Build a tool name → ToolDef lookup map from an AgentDef."""

from __future__ import annotations

from ..types_core import AgentDef, ToolDef


def build_tool_map(agent: AgentDef) -> dict[str, ToolDef]:
    """Return a mapping of tool names to their definitions."""
    return {t.name: t for t in (agent.tools or [])}
