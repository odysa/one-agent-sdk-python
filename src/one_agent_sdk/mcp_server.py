"""MCP server creation with mock/lazy pattern.

For claude-code: the real MCP server is created lazily when query() delegates
to the CLI. For other providers: tool definitions are extracted directly.

This matches the TS SDK's Symbol-based mock pattern using a sentinel key.
"""

from __future__ import annotations

from typing import Any

from .types import McpSdkServerConfig

# Sentinel key to identify mock MCP server configs
_MOCK_MCP_SERVER_KEY = "__one_agent_sdk_mock_mcp_server__"


class MockMcpServerConfig(dict):
    """A dict-like config that stores mock server options alongside the real config."""

    def __init__(self, config: dict[str, Any], mock_options: dict[str, Any]) -> None:
        super().__init__(config)
        self._mock_options = mock_options

    @property
    def mock_options(self) -> dict[str, Any]:
        return self._mock_options


def is_mock_mcp_server(config: Any) -> bool:
    """Type guard for mock MCP server configs created by create_sdk_mcp_server()."""
    return isinstance(config, MockMcpServerConfig)


def get_mock_options(config: Any) -> dict[str, Any] | None:
    """Get the mock options from a mock MCP server config."""
    if isinstance(config, MockMcpServerConfig):
        return config.mock_options
    return None


def create_sdk_mcp_server(
    name: str,
    version: str = "1.0.0",
    tools: list[Any] | None = None,
) -> McpSdkServerConfig:
    """Create an MCP server configuration for use with query().

    For claude-code: the real MCP server is created lazily when query() delegates
    to the CLI subprocess. For other providers: tool definitions are extracted
    directly from the mock config.
    """
    mock_options = {
        "name": name,
        "version": version,
        "tools": tools or [],
    }

    config = MockMcpServerConfig(
        {"type": "sdk", "name": name, "instance": None},
        mock_options,
    )
    return config  # type: ignore[return-value]


def extract_tools_from_mcp_servers(mcp_servers: dict[str, Any]) -> list[Any]:
    """Extract ToolDef-like objects from mock MCP server configs.

    Used by non-Claude providers to get tool definitions from createSdkMcpServer()
    without needing the actual MCP server.
    """
    from .types_core import ToolDef

    tools: list[ToolDef] = []
    for config in mcp_servers.values():
        if is_mock_mcp_server(config):
            mock_opts = get_mock_options(config)
            if mock_opts:
                for t in mock_opts.get("tools", []):
                    # t is a SdkMcpTool
                    if hasattr(t, "name") and hasattr(t, "handler"):
                        tools.append(ToolDef(
                            name=t.name,
                            description=getattr(t, "description", ""),
                            parameters=getattr(t, "input_schema", {}),
                            handler=_wrap_sdk_tool_handler(t),
                        ))
    return tools


def _wrap_sdk_tool_handler(t: Any) -> Any:
    """Wrap an SdkMcpTool handler to return a string (for ToolDef compatibility)."""
    import json

    async def wrapper(params: Any) -> str:
        result = await t.handler(params)
        if isinstance(result, str):
            return result
        return json.dumps(result)

    return wrapper


async def materialize_mcp_servers(
    servers: dict[str, Any],
) -> dict[str, Any]:
    """Materialize mock MCP servers into real ones for the claude-code provider.

    Replaces mock configs with real MCP server instances using the mcp package.
    """
    result: dict[str, Any] = {}
    for key, config in servers.items():
        if is_mock_mcp_server(config):
            mock_opts = get_mock_options(config)
            if mock_opts:
                result[key] = _create_real_mcp_server(mock_opts)
            else:
                result[key] = config
        else:
            result[key] = config
    return result


def _create_real_mcp_server(mock_opts: dict[str, Any]) -> McpSdkServerConfig:
    """Create a real MCP server from mock options."""
    name = mock_opts["name"]
    tool_list = mock_opts.get("tools", [])

    try:
        from mcp.server import Server
        from mcp.types import Tool as McpTool

        server = Server(name)
        tool_map: dict[str, Any] = {t.name: t for t in tool_list if hasattr(t, "name")}

        @server.list_tools()
        async def _list_tools() -> list[McpTool]:
            result = []
            for t in tool_list:
                if not hasattr(t, "name"):
                    continue
                schema = getattr(t, "input_schema", {})
                if not isinstance(schema, dict):
                    schema = {"type": "object", "properties": {}}
                elif "type" not in schema:
                    # Simple {name: type} mapping — convert
                    from . import _schema_to_json_schema
                    schema = _schema_to_json_schema(schema)
                result.append(McpTool(name=t.name, description=getattr(t, "description", ""), inputSchema=schema))
            return result

        @server.call_tool()
        async def _call_tool(tool_name: str, arguments: dict) -> Any:
            t = tool_map.get(tool_name)
            if t is None:
                return {"content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}], "isError": True}
            return await t.handler(arguments)

        return McpSdkServerConfig(type="sdk", name=name, instance=server)  # type: ignore[return-value]

    except ImportError:
        return McpSdkServerConfig(type="sdk", name=name, instance=None)  # type: ignore[return-value]
