"""Error hierarchy for the One Agent SDK."""

from __future__ import annotations


class ClaudeSDKError(Exception):
    """Base error for Claude SDK."""


class CLIConnectionError(ClaudeSDKError):
    """Failed to connect to Claude Code."""


class CLINotFoundError(CLIConnectionError):
    def __init__(
        self,
        message: str = "Claude Code not found",
        cli_path: str | None = None,
    ) -> None:
        self.cli_path = cli_path
        super().__init__(message)


class ProcessError(ClaudeSDKError):
    def __init__(
        self,
        message: str,
        exit_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(message)


class CLIJSONDecodeError(ClaudeSDKError):
    def __init__(self, line: str, original_error: Exception) -> None:
        self.line = line
        self.original_error = original_error
        super().__init__(f"Failed to decode JSON: {original_error}\nLine: {line!r}")


class MessageParseError(ClaudeSDKError):
    """Failed to parse a message from the CLI."""
