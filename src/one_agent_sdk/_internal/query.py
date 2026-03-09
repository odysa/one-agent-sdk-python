"""Query - bidirectional control protocol handler.

Handles routing of hook callbacks, permission callbacks, and MCP JSON-RPC
messages between the CLI and user-provided handlers.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

from .._errors import ProcessError
from ..types import (
    ClaudeAgentOptions,
    HookContext,
    HookMatcher,
    McpSdkServerConfig,
    Message,
)
from .message_parser import parse_message
from .transport import Transport


class Query:
    """Manages a single query lifecycle, routing messages from the transport
    through hook/permission/MCP handling and yielding typed Messages.
    """

    def __init__(
        self,
        transport: Transport,
        options: ClaudeAgentOptions,
    ) -> None:
        self._transport = transport
        self._options = options
        self._sdk_servers: dict[str, McpSdkServerConfig] = {}
        self._setup_sdk_servers()

    def _setup_sdk_servers(self) -> None:
        """Index any SDK MCP servers from options."""
        mcp = self._options.mcp_servers
        if isinstance(mcp, dict):
            for name, cfg in mcp.items():
                if isinstance(cfg, dict) and cfg.get("type") == "sdk":
                    self._sdk_servers[name] = cfg  # type: ignore[assignment]

    async def send_initial_prompt(
        self,
        prompt: str | AsyncIterable[dict[str, Any]],
    ) -> None:
        """Send the initial prompt to the CLI."""
        if isinstance(prompt, str):
            msg = {
                "type": "user",
                "message": {"role": "user", "content": prompt},
            }
            await self._transport.write(json.dumps(msg))
            await self._transport.end_input()
        else:
            # Streaming input
            async for item in prompt:
                await self._transport.write(json.dumps(item))
            await self._transport.end_input()

    async def run(
        self,
        prompt: str | AsyncIterable[dict[str, Any]],
    ) -> AsyncIterator[Message]:
        """Send prompt and yield messages, handling control protocol."""
        await self.send_initial_prompt(prompt)

        async for raw in self._transport.read_messages():
            msg_type = raw.get("type")

            # Handle control protocol messages
            if msg_type == "hook":
                await self._handle_hook(raw)
                continue

            if msg_type == "permission":
                await self._handle_permission(raw)
                continue

            if msg_type == "mcp":
                await self._handle_mcp(raw)
                continue

            # Regular message: parse and yield
            yield parse_message(raw)

    async def _handle_hook(self, raw: dict[str, Any]) -> None:
        """Handle a hook control message from the CLI."""
        hook_event = raw.get("hook_event_name", "")
        hook_id = raw.get("hook_id", "")
        input_data = raw.get("input", raw)

        hooks_config = self._options.hooks
        if not hooks_config:
            # No hooks configured: respond with empty result
            await self._respond_hook(hook_id, {})
            return

        matchers: list[HookMatcher] = hooks_config.get(hook_event, [])  # type: ignore[arg-type]
        if not matchers:
            await self._respond_hook(hook_id, {})
            return

        tool_name = input_data.get("tool_name")
        tool_use_id = raw.get("tool_use_id")
        ctx: HookContext = {"signal": None}

        result: dict[str, Any] = {}
        for matcher in matchers:
            # Check matcher pattern
            if matcher.matcher is not None:
                if tool_name is None:
                    continue
                # Simple pipe-separated match
                patterns = matcher.matcher.split("|")
                if tool_name not in patterns:
                    continue

            for callback in matcher.hooks:
                hook_result = await callback(input_data, tool_use_id, ctx)  # type: ignore[arg-type]
                if hook_result:
                    result.update(hook_result)

        # Convert Python field names to CLI field names
        serialized = self._serialize_hook_output(result)
        await self._respond_hook(hook_id, serialized)

    def _serialize_hook_output(self, output: dict[str, Any]) -> dict[str, Any]:
        """Convert Python field names (continue_, async_) to CLI names."""
        result = {}
        for key, value in output.items():
            if key == "continue_":
                result["continue"] = value
            elif key == "async_":
                result["async"] = value
            else:
                result[key] = value
        return result

    async def _respond_hook(
        self, hook_id: str, result: dict[str, Any]
    ) -> None:
        msg = {"type": "hook_response", "hook_id": hook_id, "result": result}
        await self._transport.write(json.dumps(msg))

    async def _handle_permission(self, raw: dict[str, Any]) -> None:
        """Handle a permission request from the CLI."""
        request_id = raw.get("request_id", "")
        tool_name = raw.get("tool_name", "")
        tool_input = raw.get("tool_input", {})

        can_use = self._options.can_use_tool
        if can_use is None:
            # No callback: allow by default
            await self._respond_permission(request_id, {"behavior": "allow"})
            return

        from ..types import PermissionUpdate, ToolPermissionContext

        suggestions_raw = raw.get("suggestions", [])
        suggestions: list[PermissionUpdate] = []
        for s in suggestions_raw:
            suggestions.append(
                PermissionUpdate(
                    type=s.get("type", "addRules"),
                    rules=s.get("rules"),
                    behavior=s.get("behavior"),
                    mode=s.get("mode"),
                    directories=s.get("directories"),
                    destination=s.get("destination"),
                )
            )

        ctx = ToolPermissionContext(signal=None, suggestions=suggestions)
        result = await can_use(tool_name, tool_input, ctx)

        response: dict[str, Any] = {"behavior": result.behavior}
        if hasattr(result, "updated_input") and result.updated_input is not None:  # type: ignore[union-attr]
            response["updated_input"] = result.updated_input  # type: ignore[union-attr]
        if hasattr(result, "updated_permissions") and result.updated_permissions is not None:  # type: ignore[union-attr]
            response["updated_permissions"] = [
                _serialize_permission_update(u)
                for u in result.updated_permissions  # type: ignore[union-attr]
            ]
        if hasattr(result, "message") and result.message:  # type: ignore[union-attr]
            response["message"] = result.message  # type: ignore[union-attr]
        if hasattr(result, "interrupt") and result.interrupt:  # type: ignore[union-attr]
            response["interrupt"] = result.interrupt  # type: ignore[union-attr]

        await self._respond_permission(request_id, response)

    async def _respond_permission(
        self, request_id: str, result: dict[str, Any]
    ) -> None:
        msg = {
            "type": "permission_response",
            "request_id": request_id,
            "result": result,
        }
        await self._transport.write(json.dumps(msg))

    async def _handle_mcp(self, raw: dict[str, Any]) -> None:
        """Route MCP JSON-RPC messages to in-process SDK servers."""
        server_name = raw.get("server_name", "")
        request_id = raw.get("request_id", "")

        server_cfg = self._sdk_servers.get(server_name)
        if not server_cfg:
            await self._respond_mcp(
                request_id,
                server_name,
                {"error": {"code": -32601, "message": f"Unknown SDK server: {server_name}"}},
            )
            return

        # Route the JSON-RPC request to the MCP server instance
        instance = server_cfg.get("instance")
        if instance is None:
            await self._respond_mcp(
                request_id,
                server_name,
                {"error": {"code": -32603, "message": "Server instance not available"}},
            )
            return

        jsonrpc_request = raw.get("request", {})
        try:
            # Call the MCP server's handle_request method
            if hasattr(instance, "handle_json_rpc"):
                result = await instance.handle_json_rpc(jsonrpc_request)
            else:
                result = {"error": {"code": -32603, "message": "Server does not support JSON-RPC"}}
        except Exception as exc:
            result = {"error": {"code": -32603, "message": str(exc)}}

        await self._respond_mcp(request_id, server_name, result)

    async def _respond_mcp(
        self,
        request_id: str,
        server_name: str,
        result: dict[str, Any],
    ) -> None:
        msg = {
            "type": "mcp_response",
            "request_id": request_id,
            "server_name": server_name,
            "result": result,
        }
        await self._transport.write(json.dumps(msg))


def _serialize_permission_update(update: Any) -> dict[str, Any]:
    """Serialize a PermissionUpdate dataclass to a dict for the CLI."""
    result: dict[str, Any] = {"type": update.type}
    if update.rules is not None:
        result["rules"] = [
            {"tool_name": r.tool_name, "rule_content": r.rule_content}
            for r in update.rules
        ]
    if update.behavior is not None:
        result["behavior"] = update.behavior
    if update.mode is not None:
        result["mode"] = update.mode
    if update.directories is not None:
        result["directories"] = update.directories
    if update.destination is not None:
        result["destination"] = update.destination
    return result
