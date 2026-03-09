"""Session listing and message retrieval utilities."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from ..types import SDKSessionInfo, SessionMessage


def _get_sessions_dir() -> Path:
    """Return the default Claude sessions directory."""
    return Path.home() / ".claude" / "projects"


def _find_session_files(
    directory: str | None = None,
    include_worktrees: bool = True,
) -> list[Path]:
    """Find all session JSONL files, optionally filtered by directory."""
    sessions_dir = _get_sessions_dir()
    if not sessions_dir.exists():
        return []

    files: list[Path] = []
    for project_dir in sessions_dir.iterdir():
        if not project_dir.is_dir():
            continue

        # If filtering by directory, check if the project dir matches
        if directory is not None:
            # Claude stores projects under a mangled path name
            normalized = directory.replace("/", "-").strip("-")
            if normalized not in project_dir.name:
                continue

        for session_file in project_dir.glob("*.jsonl"):
            files.append(session_file)

    return files


def _parse_session_file(path: Path) -> SDKSessionInfo | None:
    """Parse a session JSONL file into session info."""
    try:
        stat = path.stat()
    except OSError:
        return None

    session_id = path.stem
    summary = session_id
    custom_title: str | None = None
    first_prompt: str | None = None
    git_branch: str | None = None
    cwd: str | None = None

    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")
                if msg_type == "system":
                    subtype = data.get("subtype", "")
                    if subtype == "session_info":
                        custom_title = data.get("custom_title")
                        git_branch = data.get("git_branch")
                        cwd = data.get("cwd")
                elif msg_type == "user" and first_prompt is None:
                    msg = data.get("message", {})
                    content = msg.get("content", "")
                    if isinstance(content, str) and content.strip():
                        first_prompt = content.strip()

                # Only read enough lines to get metadata
                if custom_title is not None or first_prompt is not None:
                    break
    except OSError:
        return None

    if custom_title:
        summary = custom_title
    elif first_prompt:
        summary = first_prompt[:100]

    return SDKSessionInfo(
        session_id=session_id,
        summary=summary,
        last_modified=int(stat.st_mtime * 1000),
        file_size=stat.st_size,
        custom_title=custom_title,
        first_prompt=first_prompt,
        git_branch=git_branch,
        cwd=cwd,
    )


def list_sessions(
    directory: str | None = None,
    limit: int | None = None,
    include_worktrees: bool = True,
) -> list[SDKSessionInfo]:
    """List past sessions with metadata.

    Results are sorted by ``last_modified`` descending (newest first).
    """
    files = _find_session_files(directory, include_worktrees)
    sessions: list[SDKSessionInfo] = []

    for path in files:
        info = _parse_session_file(path)
        if info is not None:
            sessions.append(info)

    # Sort by last_modified descending
    sessions.sort(key=lambda s: s.last_modified, reverse=True)

    if limit is not None:
        sessions = sessions[:limit]

    return sessions


def get_session_messages(
    session_id: str,
    directory: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[SessionMessage]:
    """Retrieve messages from a past session."""
    files = _find_session_files(directory)

    # Find the matching session file
    target: Path | None = None
    for f in files:
        if f.stem == session_id:
            target = f
            break

    if target is None:
        return []

    messages: list[SessionMessage] = []
    try:
        with open(target) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")
                if msg_type in ("user", "assistant"):
                    messages.append(
                        SessionMessage(
                            type=msg_type,
                            uuid=data.get("uuid", ""),
                            session_id=session_id,
                            message=data.get("message"),
                        )
                    )
    except OSError:
        return []

    # Apply offset and limit
    messages = messages[offset:]
    if limit is not None:
        messages = messages[:limit]

    return messages
