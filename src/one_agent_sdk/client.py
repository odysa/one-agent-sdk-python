"""Public ClaudeSDKClient class."""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

from ._internal.client import InternalClient
from ._internal.transport import Transport
from .types import (
    ClaudeAgentOptions,
    McpServerConfig,
    McpServerStatus,
    Message,
    ResultMessage,
)


class ClaudeSDKClient:
    """Maintains a conversation session across multiple exchanges.

    Supports async context manager for automatic connection management::

        async with ClaudeSDKClient() as client:
            await client.query("Hello Claude")
            async for message in client.receive_response():
                print(message)
    """

    def __init__(
        self,
        options: ClaudeAgentOptions | None = None,
        transport: Transport | None = None,
    ) -> None:
        self._client = InternalClient(options, transport)

    async def __aenter__(self) -> ClaudeSDKClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.disconnect()

    async def connect(
        self,
        prompt: str | AsyncIterable[dict[str, Any]] | None = None,
    ) -> None:
        """Connect to Claude with an optional initial prompt."""
        await self._client.connect(prompt)

    async def query(
        self,
        prompt: str | AsyncIterable[dict[str, Any]],
        session_id: str = "default",
    ) -> None:
        """Send a new request in streaming mode."""
        await self._client.send_query(prompt)

    async def receive_messages(self) -> AsyncIterator[Message]:
        """Receive all messages from Claude as an async iterator."""
        async for msg in self._client.receive_messages():
            yield msg

    async def receive_response(self) -> AsyncIterator[Message]:
        """Receive messages until and including a ResultMessage."""
        async for msg in self._client.receive_messages():
            yield msg
            if isinstance(msg, ResultMessage):
                return

    async def interrupt(self) -> None:
        """Send interrupt signal."""
        await self._client.interrupt()

    async def set_permission_mode(self, mode: str) -> None:
        """Change the permission mode for the current session."""
        await self._client.set_permission_mode(mode)

    async def set_model(self, model: str | None = None) -> None:
        """Change the model. Pass None to reset to default."""
        await self._client.set_model(model)

    async def rewind_files(self, user_message_id: str) -> None:
        """Restore files to their state at the specified user message."""
        await self._client.rewind_files(user_message_id)

    async def get_mcp_status(self) -> list[McpServerStatus]:
        """Get the status of all configured MCP servers."""
        return await self._client.get_mcp_status()

    async def add_mcp_server(
        self, name: str, config: McpServerConfig
    ) -> None:
        """Add an MCP server to the running session."""
        await self._client.add_mcp_server(name, config)

    async def remove_mcp_server(self, name: str) -> None:
        """Remove an MCP server from the running session."""
        await self._client.remove_mcp_server(name)

    async def get_server_info(self) -> dict[str, Any] | None:
        """Get server information."""
        return await self._client.get_server_info()

    async def disconnect(self) -> None:
        """Disconnect from Claude."""
        await self._client.disconnect()
