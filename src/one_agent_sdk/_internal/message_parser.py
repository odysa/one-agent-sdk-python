"""Parse raw dicts from the CLI into typed Message objects."""

from __future__ import annotations

from typing import Any

from .._errors import MessageParseError
from ..types import (
    AssistantMessage,
    ContentBlock,
    Message,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TaskNotificationMessage,
    TaskProgressMessage,
    TaskStartedMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)


def _parse_content_block(raw: dict[str, Any]) -> ContentBlock:
    """Convert a raw dict to a ContentBlock."""
    block_type = raw.get("type")
    if block_type == "text":
        return TextBlock(text=raw.get("text", ""))
    if block_type == "thinking":
        return ThinkingBlock(
            thinking=raw.get("thinking", ""),
            signature=raw.get("signature", ""),
        )
    if block_type == "tool_use":
        return ToolUseBlock(
            id=raw.get("id", ""),
            name=raw.get("name", ""),
            input=raw.get("input", {}),
        )
    if block_type == "tool_result":
        return ToolResultBlock(
            tool_use_id=raw.get("tool_use_id", ""),
            content=raw.get("content"),
            is_error=raw.get("is_error"),
        )
    # Fallback: treat unknown block as text
    return TextBlock(text=str(raw))


def _parse_content(raw: Any) -> str | list[ContentBlock]:
    """Parse content field which can be a string or list of blocks."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return [_parse_content_block(b) if isinstance(b, dict) else TextBlock(text=str(b)) for b in raw]
    return str(raw)


def _parse_content_blocks(raw: Any) -> list[ContentBlock]:
    """Parse content that must be a list of blocks."""
    if isinstance(raw, list):
        return [_parse_content_block(b) if isinstance(b, dict) else TextBlock(text=str(b)) for b in raw]
    return []


def parse_message(data: dict[str, Any]) -> Message:
    """Convert a raw dictionary from the CLI into a typed Message object.

    The CLI sends JSON lines, each with a ``type`` field that indicates the
    message kind.
    """
    msg_type = data.get("type")

    if msg_type == "user":
        msg_data = data.get("message", data)
        return UserMessage(
            content=_parse_content(msg_data.get("content", "")),
            uuid=data.get("uuid"),
            parent_tool_use_id=data.get("parent_tool_use_id"),
            tool_use_result=data.get("tool_use_result"),
        )

    if msg_type == "assistant":
        msg_data = data.get("message", data)
        return AssistantMessage(
            content=_parse_content_blocks(msg_data.get("content", [])),
            model=msg_data.get("model", ""),
            parent_tool_use_id=data.get("parent_tool_use_id"),
            error=msg_data.get("error"),
        )

    if msg_type == "result":
        return ResultMessage(
            subtype=data.get("subtype", "result"),
            duration_ms=data.get("duration_ms", 0),
            duration_api_ms=data.get("duration_api_ms", 0),
            is_error=data.get("is_error", False),
            num_turns=data.get("num_turns", 0),
            session_id=data.get("session_id", ""),
            total_cost_usd=data.get("total_cost_usd"),
            usage=data.get("usage"),
            result=data.get("result"),
            stop_reason=data.get("stop_reason"),
            structured_output=data.get("structured_output"),
        )

    if msg_type == "system":
        subtype = data.get("subtype", "")

        # Task-specific subtypes
        if subtype == "task_started":
            return TaskStartedMessage(
                subtype=subtype,
                data=data,
                task_id=data.get("task_id", ""),
                description=data.get("description", ""),
                uuid=data.get("uuid", ""),
                session_id=data.get("session_id", ""),
                tool_use_id=data.get("tool_use_id"),
                task_type=data.get("task_type"),
            )
        if subtype == "task_progress":
            return TaskProgressMessage(
                subtype=subtype,
                data=data,
                task_id=data.get("task_id", ""),
                description=data.get("description", ""),
                usage=data.get("usage", {"total_tokens": 0, "tool_uses": 0, "duration_ms": 0}),
                uuid=data.get("uuid", ""),
                session_id=data.get("session_id", ""),
                tool_use_id=data.get("tool_use_id"),
                last_tool_name=data.get("last_tool_name"),
            )
        if subtype == "task_notification":
            return TaskNotificationMessage(
                subtype=subtype,
                data=data,
                task_id=data.get("task_id", ""),
                status=data.get("status", "completed"),
                output_file=data.get("output_file", ""),
                summary=data.get("summary", ""),
                uuid=data.get("uuid", ""),
                session_id=data.get("session_id", ""),
                tool_use_id=data.get("tool_use_id"),
                usage=data.get("usage"),
            )

        return SystemMessage(subtype=subtype, data=data)

    if msg_type == "stream_event":
        return StreamEvent(
            uuid=data.get("uuid", ""),
            session_id=data.get("session_id", ""),
            event=data.get("event", {}),
            parent_tool_use_id=data.get("parent_tool_use_id"),
        )

    # Unknown type: wrap as SystemMessage
    return SystemMessage(subtype=data.get("subtype", "unknown"), data=data)
