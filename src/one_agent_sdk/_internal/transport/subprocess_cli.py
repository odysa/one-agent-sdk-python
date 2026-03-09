"""SubprocessCLITransport - wraps the Claude Code CLI as a subprocess."""

from __future__ import annotations

import json
import os
import shutil
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import subprocess

import anyio
import anyio.abc

from ..._errors import CLIJSONDecodeError, CLINotFoundError, ProcessError
from ...types import ClaudeAgentOptions
from . import Transport

# Default max buffer size: 100 MB
_DEFAULT_MAX_BUFFER_SIZE = 100 * 1024 * 1024


def _find_cli(cli_path: str | Path | None = None) -> str:
    """Locate the Claude Code CLI binary.

    Search order:
    1. Explicit ``cli_path`` argument.
    2. ``claude`` on ``$PATH``.
    3. Common npm / yarn global install locations.
    """
    if cli_path is not None:
        p = str(cli_path)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
        raise CLINotFoundError(
            f"Specified CLI path not found or not executable: {p}",
            cli_path=p,
        )

    # Check PATH
    found = shutil.which("claude")
    if found:
        return found

    # Common global install dirs
    home = Path.home()
    candidates = [
        home / ".npm-global" / "bin" / "claude",
        home / ".yarn" / "bin" / "claude",
        Path("/usr/local/bin/claude"),
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)

    raise CLINotFoundError()


def _build_cli_args(options: ClaudeAgentOptions) -> list[str]:
    """Build the argument list for the CLI subprocess."""
    args: list[str] = [
        "--output-format",
        "stream-json",
        "--verbose",
        "--input-format",
        "stream-json",
    ]

    if options.model:
        args.extend(["--model", options.model])
    if options.permission_mode:
        args.extend(["--permission-mode", options.permission_mode])
    if options.system_prompt and isinstance(options.system_prompt, str):
        args.extend(["--system-prompt", options.system_prompt])
    if options.continue_conversation:
        args.append("--continue")
    if options.resume:
        args.extend(["--resume", options.resume])
    if options.max_turns is not None:
        args.extend(["--max-turns", str(options.max_turns)])
    if options.cwd:
        args.extend(["--cwd", str(options.cwd)])
    if options.settings:
        args.extend(["--settings", options.settings])
    if options.user:
        args.extend(["--user", options.user])
    if options.fallback_model:
        args.extend(["--fallback-model", options.fallback_model])

    for tool in options.allowed_tools:
        args.extend(["--allowedTools", tool])
    for tool in options.disallowed_tools:
        args.extend(["--disallowedTools", tool])
    for d in options.add_dirs:
        args.extend(["--add-dir", str(d)])
    for beta in options.betas:
        args.extend(["--beta", beta])
    if options.max_thinking_tokens is not None:
        args.extend(["--max-thinking-tokens", str(options.max_thinking_tokens)])
    if options.enable_file_checkpointing:
        args.append("--enable-file-checkpointing")
    if options.fork_session:
        args.append("--fork-session")

    # Extra args passthrough
    for key, val in options.extra_args.items():
        if val is not None:
            args.extend([key, val])
        else:
            args.append(key)

    return args


class SubprocessCLITransport(Transport):
    """Transport that communicates with the Claude Code CLI via subprocess."""

    def __init__(self, options: ClaudeAgentOptions | None = None) -> None:
        self._options = options or ClaudeAgentOptions()
        self._process: anyio.abc.Process | None = None
        self._ready = False
        self._max_buffer_size = (
            self._options.max_buffer_size or _DEFAULT_MAX_BUFFER_SIZE
        )

    async def connect(self) -> None:
        cli = _find_cli(self._options.cli_path)
        args = _build_cli_args(self._options)

        env = {**os.environ, **self._options.env}

        self._process = await anyio.open_process(
            [cli, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=str(self._options.cwd) if self._options.cwd else None,
        )
        self._ready = True

    async def write(self, data: str) -> None:
        if not self._process or not self._process.stdin:
            raise ProcessError("Transport not connected")
        line = data if data.endswith("\n") else data + "\n"
        await self._process.stdin.send(line.encode())

    async def read_messages(self) -> AsyncIterator[dict[str, Any]]:
        if not self._process or not self._process.stdout:
            raise ProcessError("Transport not connected")

        buffer = b""
        async for chunk in self._process.stdout:
            buffer += chunk

            # Guard against unbounded buffer
            if len(buffer) > self._max_buffer_size:
                buffer = buffer[-self._max_buffer_size :]

            while b"\n" in buffer:
                line_bytes, buffer = buffer.split(b"\n", 1)
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    # Try speculative parsing: accumulate until valid JSON
                    raise CLIJSONDecodeError(line, exc)

        # Process remaining buffer
        remaining = buffer.decode("utf-8", errors="replace").strip()
        if remaining:
            try:
                yield json.loads(remaining)
            except json.JSONDecodeError:
                pass  # Ignore trailing non-JSON

    async def close(self) -> None:
        self._ready = False
        if self._process:
            if self._process.stdin:
                await self._process.stdin.aclose()
            self._process.terminate()
            try:
                with anyio.fail_after(5):
                    await self._process.wait()
            except TimeoutError:
                self._process.kill()
            self._process = None

    def is_ready(self) -> bool:
        return self._ready

    async def end_input(self) -> None:
        if self._process and self._process.stdin:
            await self._process.stdin.aclose()
