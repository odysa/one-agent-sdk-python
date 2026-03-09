"""InternalClient - orchestrates transport + query processing."""

from __future__ import annotations

import json
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

from .._errors import ProcessError
from ..types import ClaudeAgentOptions, McpServerConfig, McpServerStatus, Message
from .query import Query
from .transport import Transport
from .transport.subprocess_cli import SubprocessCLITransport


class InternalClient:
    """Low-level client that manages the transport lifecycle and
    delegates message processing to a ``Query`` instance.
    """

    def __init__(
        self,
        options: ClaudeAgentOptions | None = None,
        transport: Transport | None = None,
    ) -> None:
        self._options = options or ClaudeAgentOptions()
        self._transport = transport
        self._owns_transport = transport is None
        self._query: Query | None = None

    async def connect(
        self,
        prompt: str | AsyncIterable[dict[str, Any]] | None = None,
    ) -> None:
        """Connect the transport. Optionally send an initial prompt."""
        if self._transport is None:
            self._transport = SubprocessCLITransport(self._options)
            self._owns_transport = True

        if not self._transport.is_ready():
            await self._transport.connect()

        self._query = Query(self._transport, self._options)

        if prompt is not None:
            await self._query.send_initial_prompt(prompt)

    async def send_query(
        self,
        prompt: str | AsyncIterable[dict[str, Any]],
    ) -> None:
        """Send a new query to the CLI."""
        if self._transport is None or not self._transport.is_ready():
            raise ProcessError("Client not connected")

        self._query = Query(self._transport, self._options)
        await self._query.send_initial_prompt(prompt)

    async def receive_messages(self) -> AsyncIterator[Message]:
        """Yield all messages from the current query."""
        if self._query is None or self._transport is None:
            raise ProcessError("No active query")

        async for raw in self._transport.read_messages():
            msg_type = raw.get("type")

            # Delegate control messages
            if msg_type == "hook":
                await self._query._handle_hook(raw)
                continue
            if msg_type == "permission":
                await self._query._handle_permission(raw)
                continue
            if msg_type == "mcp":
                await self._query._handle_mcp(raw)
                continue

            from .message_parser import parse_message

            yield parse_message(raw)

    async def interrupt(self) -> None:
        """Send an interrupt signal to the CLI."""
        if self._transport and self._transport.is_ready():
            msg = {"type": "interrupt"}
            await self._transport.write(json.dumps(msg))

    async def set_permission_mode(self, mode: str) -> None:
        """Change the permission mode."""
        if self._transport and self._transport.is_ready():
            msg = {"type": "command", "command": "set_permission_mode", "mode": mode}
            await self._transport.write(json.dumps(msg))

    async def set_model(self, model: str | None = None) -> None:
        """Change the model."""
        if self._transport and self._transport.is_ready():
            msg = {"type": "command", "command": "set_model", "model": model}
            await self._transport.write(json.dumps(msg))

    async def rewind_files(self, user_message_id: str) -> None:
        """Restore files to state at the given user message."""
        if self._transport and self._transport.is_ready():
            msg = {
                "type": "command",
                "command": "rewind_files",
                "user_message_id": user_message_id,
            }
            await self._transport.write(json.dumps(msg))

    async def get_mcp_status(self) -> list[McpServerStatus]:
        """Get MCP server status."""
        if self._transport and self._transport.is_ready():
            msg = {"type": "command", "command": "get_mcp_status"}
            await self._transport.write(json.dumps(msg))
        # The response will come via read_messages; return empty for now.
        return []

    async def add_mcp_server(
        self, name: str, config: McpServerConfig
    ) -> None:
        """Add an MCP server."""
        if self._transport and self._transport.is_ready():
            msg = {
                "type": "command",
                "command": "add_mcp_server",
                "name": name,
                "config": config,
            }
            await self._transport.write(json.dumps(msg))

    async def remove_mcp_server(self, name: str) -> None:
        """Remove an MCP server."""
        if self._transport and self._transport.is_ready():
            msg = {
                "type": "command",
                "command": "remove_mcp_server",
                "name": name,
            }
            await self._transport.write(json.dumps(msg))

    async def get_server_info(self) -> dict[str, Any] | None:
        """Get server info."""
        if self._transport and self._transport.is_ready():
            msg = {"type": "command", "command": "get_server_info"}
            await self._transport.write(json.dumps(msg))
        return None

    async def disconnect(self) -> None:
        """Disconnect and clean up."""
        if self._transport and self._owns_transport:
            await self._transport.close()
        self._transport = None
        self._query = None
