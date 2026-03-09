"""One Agent SDK - drop-in replacement for claude-agent-sdk-python
with multi-provider support.

Usage::

    from one_agent_sdk import query, ClaudeSDKClient, ClaudeAgentOptions

    async for message in query(prompt="Hello"):
        print(message)

100% API-compatible with @anthropic-ai/claude-agent-sdk.
Pass ``options.provider`` to route to a different backend (codex, copilot, kimi-cli, etc.).
Defaults to claude-code when no provider is specified.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from ._errors import (
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    ClaudeSDKError,
    MessageParseError,
    ProcessError,
)
from ._internal.delegates import (
    unstable_v2_create_session,
    unstable_v2_prompt,
    unstable_v2_resume_session,
)
from ._internal.sessions import get_session_messages, list_sessions
from ._internal.transport import Transport
from ._version import __version__
from .client import ClaudeSDKClient
from .mcp_server import (
    create_sdk_mcp_server as _create_sdk_mcp_server_mock,
    extract_tools_from_mcp_servers,
    is_mock_mcp_server,
    materialize_mcp_servers,
)
from .query import query
from .types import (
    AbortError,
    AccountInfo,
    AgentDefinition,
    AgentInfo,
    ApiKeySource,
    AssistantMessage,
    AssistantMessageError,
    AsyncHookJSONOutput,
    BaseHookInput,
    BetaMessage,
    BetaRawMessageStreamEvent,
    BetaUsage,
    CallToolResult,
    CanUseTool,
    ClaudeAgentOptions,
    ConfigChangeHookInput,
    ConfigScope,
    ContentBlock,
    ElicitationHookInput,
    ElicitationHookSpecificOutput,
    ElicitationRequest,
    ElicitationResult,
    ElicitationResultHookInput,
    ElicitationResultHookSpecificOutput,
    EXIT_REASONS,
    ExitReason,
    FastModeState,
    GetSessionMessagesOptions,
    HOOK_EVENTS,
    HookCallback,
    HookCallbackMatcher,
    HookContext,
    HookEvent,
    HookJSONOutput,
    HookMatcher,
    HookSpecificOutput,
    InstructionsLoadedHookInput,
    JsonSchemaOutputFormat,
    ListSessionsOptions,
    McpClaudeAIProxyServerConfig,
    McpHttpServerConfig,
    McpSdkServerConfig,
    McpSdkServerConfigWithInstance,
    McpServerConfig,
    McpServerConfigForProcessTransport,
    McpServerConnectionStatus,
    McpServerInfo,
    McpServerStatus,
    McpServerStatusConfig,
    McpSetServersResult,
    McpSSEServerConfig,
    McpStdioServerConfig,
    McpToolInfo,
    Message,
    MessageParam,
    ModelInfo,
    ModelUsage,
    NonNullableUsage,
    NotificationHookInput,
    NotificationHookSpecificOutput,
    OnElicitation,
    OutputFormat,
    OutputFormatType,
    PermissionBehavior,
    PermissionMode,
    PermissionRequestHookInput,
    PermissionRequestHookSpecificOutput,
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    PermissionRuleValue,
    PermissionUpdate,
    PermissionUpdateDestination,
    PostToolUseFailureHookInput,
    PostToolUseFailureHookSpecificOutput,
    PostToolUseHookInput,
    PostToolUseHookSpecificOutput,
    PreCompactHookInput,
    PreToolUseHookInput,
    PreToolUseHookSpecificOutput,
    PromptRequest,
    PromptRequestOption,
    PromptResponse,
    ResultMessage,
    RewindFilesResult,
    SandboxFilesystemConfig,
    SandboxIgnoreViolations,
    SandboxNetworkConfig,
    SandboxSettings,
    SDKAssistantMessage,
    SDKAuthStatusMessage,
    SdkBeta,
    SDKCompactBoundaryMessage,
    SDKControlInitializeResponse,
    SDKElicitationCompleteMessage,
    SDKFilesPersistedEvent,
    SDKHookProgressMessage,
    SDKHookResponseMessage,
    SDKHookStartedMessage,
    SDKLocalCommandOutputMessage,
    SdkMcpTool,
    SDKMessage,
    SDKPartialAssistantMessage,
    SDKPermissionDenial,
    SdkPluginConfig,
    SDKPromptSuggestionMessage,
    SDKRateLimitEvent,
    SDKRateLimitInfo,
    SDKResultError,
    SDKResultMessage,
    SDKResultSuccess,
    SDKSessionInfo,
    SDKSessionOptions,
    SDKStatus,
    SDKStatusMessage,
    SDKSystemMessage,
    SDKTaskNotificationMessage,
    SDKTaskProgressMessage,
    SDKTaskStartedMessage,
    SDKToolProgressMessage,
    SDKToolUseSummaryMessage,
    SDKUserMessage,
    SDKUserMessageReplay,
    SessionEndHookInput,
    SessionMessage,
    SessionStartHookInput,
    SessionStartHookSpecificOutput,
    Settings,
    SettingSource,
    SetupHookInput,
    SetupHookSpecificOutput,
    SlashCommand,
    SpawnOptions,
    StopHookInput,
    StreamEvent,
    SubagentStartHookInput,
    SubagentStartHookSpecificOutput,
    SubagentStopHookInput,
    SyncHookJSONOutput,
    SystemMessage,
    SystemPromptPreset,
    TaskCompletedHookInput,
    TaskNotificationMessage,
    TaskNotificationStatus,
    TaskProgressMessage,
    TaskStartedMessage,
    TaskUsage,
    TeammateIdleHookInput,
    TextBlock,
    ThinkingBlock,
    ThinkingConfig,
    ThinkingConfigAdaptive,
    ThinkingConfigDisabled,
    ThinkingConfigEnabled,
    ToolAnnotations,
    ToolConfig,
    ToolPermissionContext,
    ToolResultBlock,
    ToolsPreset,
    ToolUseBlock,
    UserMessage,
    UserPromptSubmitHookInput,
    UserPromptSubmitHookSpecificOutput,
    WorktreeCreateHookInput,
    WorktreeRemoveHookInput,
)

# Multi-provider types
from .types_core import (
    AgentDef,
    AgentMcpServerConfig,
    AgentRun,
    BuiltinProvider,
    DoneChunk,
    ErrorChunk,
    HandoffChunk,
    Middleware,
    MiddlewareContext,
    Provider,
    ProviderBackend,
    RunConfig,
    StreamChunk,
    TextChunk,
    ToolCallChunk,
    ToolDef,
    ToolResultChunk,
    UsageInfo,
)

# Provider system
from .providers import create_provider
from .registry import ProviderFactory, clear_providers, register_provider

# Middleware
from .middleware import (
    FilterOptions,
    GuardrailsOptions,
    HooksOptions,
    LoggingOptions,
    TextCollectorHandle,
    TextCollectorOptions,
    TimingHandle,
    TimingInfo,
    TimingOptions,
    UsageStats,
    UsageTrackerHandle,
    UsageTrackerOptions,
    apply_middleware,
    define_middleware,
    filter,
    guardrails,
    hooks,
    logging,
    text_collector,
    timing,
    usage_tracker,
)

# Session
from .session import (
    MemoryStore,
    Session,
    SessionConfig,
    SessionStore,
    create_session,
)
from .session import SessionMessage as ConversationMessage  # avoid clash with types.SessionMessage

# Runner (deprecated)
from .runner import run, run_to_completion

# Utils
from .utils import build_tool_map, extract_json, handoff_tool_name, parse_handoff


# ---------------------------------------------------------------------------
# tool() decorator
# ---------------------------------------------------------------------------

_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def _schema_to_json_schema(schema: type | dict[str, Any]) -> dict[str, Any]:
    """Convert a simple type mapping or JSON Schema dict to JSON Schema."""
    if isinstance(schema, dict):
        # Check if already JSON Schema
        if "type" in schema and schema["type"] == "object":
            return schema
        # Simple {name: type} mapping
        properties: dict[str, Any] = {}
        required: list[str] = []
        for name, typ in schema.items():
            if isinstance(typ, type) and typ in _TYPE_MAP:
                properties[name] = {"type": _TYPE_MAP[typ]}
            elif isinstance(typ, dict):
                properties[name] = typ
            else:
                properties[name] = {"type": "string"}
            required.append(name)
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }
    # If it's a class type, use its name
    return {"type": "object", "properties": {}}


def tool(
    name: str,
    description: str,
    input_schema: type | dict[str, Any],
    annotations: Any | None = None,
) -> Callable[[Callable[[Any], Awaitable[dict[str, Any]]]], SdkMcpTool[Any]]:
    """Decorator for defining MCP tools with type safety.

    Usage::

        @tool("greet", "Greet a user", {"name": str})
        async def greet(args: dict[str, Any]) -> dict[str, Any]:
            return {"content": [{"type": "text", "text": f"Hello, {args['name']}!"}]}
    """

    def decorator(
        func: Callable[[Any], Awaitable[dict[str, Any]]],
    ) -> SdkMcpTool[Any]:
        return SdkMcpTool(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=func,
            annotations=annotations,
        )

    return decorator


# ---------------------------------------------------------------------------
# create_sdk_mcp_server()
# ---------------------------------------------------------------------------


def create_sdk_mcp_server(
    name: str,
    version: str = "1.0.0",
    tools: list[SdkMcpTool[Any]] | None = None,
) -> McpSdkServerConfig:
    """Create an in-process MCP server.

    Returns an :class:`McpSdkServerConfig` that can be passed to
    ``ClaudeAgentOptions.mcp_servers``.

    Usage::

        @tool("add", "Add two numbers", {"a": float, "b": float})
        async def add(args):
            return {"content": [{"type": "text", "text": str(args["a"] + args["b"])}]}

        server = create_sdk_mcp_server("calculator", tools=[add])
        options = ClaudeAgentOptions(mcp_servers={"calc": server})
    """
    try:
        from mcp.server import Server
        from mcp.types import Tool as McpTool

        server = Server(name)

        tool_list = tools or []
        tool_map: dict[str, SdkMcpTool[Any]] = {t.name: t for t in tool_list}

        @server.list_tools()
        async def _list_tools() -> list[McpTool]:
            result = []
            for t in tool_list:
                json_schema = _schema_to_json_schema(t.input_schema)
                mcp_tool = McpTool(
                    name=t.name,
                    description=t.description,
                    inputSchema=json_schema,
                )
                result.append(mcp_tool)
            return result

        @server.call_tool()
        async def _call_tool(
            tool_name: str, arguments: dict[str, Any]
        ) -> Any:
            t = tool_map.get(tool_name)
            if t is None:
                return {"content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}], "isError": True}
            return await t.handler(arguments)

        return McpSdkServerConfig(type="sdk", name=name, instance=server)

    except ImportError:
        # mcp package not available - create a lightweight stub
        return McpSdkServerConfig(type="sdk", name=name, instance=None)


# ---------------------------------------------------------------------------
# Deprecated helpers (for parity with TS SDK)
# ---------------------------------------------------------------------------


def define_agent(
    *,
    name: str,
    description: str,
    prompt: str,
    tools: list[ToolDef] | None = None,
    handoffs: list[str] | None = None,
    model: str | None = None,
    mcp_servers: dict[str, AgentMcpServerConfig] | None = None,
) -> AgentDef:
    """Convenience helper to define an agent with type checking.

    .. deprecated::
        Will be removed in v0.2. Use ``AgentDef`` directly.
    """
    import warnings

    warnings.warn("define_agent() is deprecated, use AgentDef directly", DeprecationWarning, stacklevel=2)
    return AgentDef(
        name=name,
        description=description,
        prompt=prompt,
        tools=tools,
        handoffs=handoffs,
        model=model,
        mcp_servers=mcp_servers,
    )


def define_tool(
    *,
    name: str,
    description: str,
    parameters: Any,
    handler: Callable[..., Awaitable[str]],
) -> ToolDef:
    """Convenience helper to define a tool with type-safe parameters.

    .. deprecated::
        Will be removed in v0.2. Use ``tool()`` instead.
    """
    import warnings

    warnings.warn("define_tool() is deprecated, use tool() instead", DeprecationWarning, stacklevel=2)
    return ToolDef(name=name, description=description, parameters=parameters, handler=handler)


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    # Version
    "__version__",
    # Core functions
    "query",
    "tool",
    "create_sdk_mcp_server",
    "list_sessions",
    "get_session_messages",
    # v2 unstable APIs
    "unstable_v2_create_session",
    "unstable_v2_prompt",
    "unstable_v2_resume_session",
    # MCP server utilities
    "is_mock_mcp_server",
    "extract_tools_from_mcp_servers",
    "materialize_mcp_servers",
    # Client
    "ClaudeSDKClient",
    # Transport
    "Transport",
    # Options
    "ClaudeAgentOptions",
    # Messages
    "Message",
    "UserMessage",
    "AssistantMessage",
    "AssistantMessageError",
    "SystemMessage",
    "ResultMessage",
    "StreamEvent",
    # Content blocks
    "ContentBlock",
    "TextBlock",
    "ThinkingBlock",
    "ToolUseBlock",
    "ToolResultBlock",
    # Task messages
    "TaskStartedMessage",
    "TaskProgressMessage",
    "TaskNotificationMessage",
    "TaskUsage",
    "TaskNotificationStatus",
    # MCP types
    "SdkMcpTool",
    "McpServerConfig",
    "McpStdioServerConfig",
    "McpSSEServerConfig",
    "McpHttpServerConfig",
    "McpSdkServerConfig",
    "McpSdkServerConfigWithInstance",
    "McpClaudeAIProxyServerConfig",
    "McpServerConfigForProcessTransport",
    "McpServerStatusConfig",
    "McpSetServersResult",
    "McpServerStatus",
    "McpServerConnectionStatus",
    "McpServerInfo",
    "McpToolInfo",
    # Permission types
    "PermissionMode",
    "PermissionBehavior",
    "PermissionResult",
    "PermissionResultAllow",
    "PermissionResultDeny",
    "PermissionUpdate",
    "PermissionUpdateDestination",
    "PermissionRuleValue",
    "CanUseTool",
    "ToolPermissionContext",
    # Hook types
    "HookEvent",
    "HOOK_EVENTS",
    "HookCallback",
    "HookCallbackMatcher",
    "HookContext",
    "HookMatcher",
    "HookInput",
    "HookJSONOutput",
    "HookSpecificOutput",
    "SyncHookJSONOutput",
    "AsyncHookJSONOutput",
    "BaseHookInput",
    "PreToolUseHookInput",
    "PostToolUseHookInput",
    "PostToolUseFailureHookInput",
    "UserPromptSubmitHookInput",
    "StopHookInput",
    "SubagentStopHookInput",
    "PreCompactHookInput",
    "NotificationHookInput",
    "SubagentStartHookInput",
    "PermissionRequestHookInput",
    "SessionStartHookInput",
    "SessionEndHookInput",
    "SetupHookInput",
    "TeammateIdleHookInput",
    "TaskCompletedHookInput",
    "ElicitationHookInput",
    "ElicitationResultHookInput",
    "ConfigChangeHookInput",
    "InstructionsLoadedHookInput",
    "WorktreeCreateHookInput",
    "WorktreeRemoveHookInput",
    "PreToolUseHookSpecificOutput",
    "PostToolUseHookSpecificOutput",
    "PostToolUseFailureHookSpecificOutput",
    "UserPromptSubmitHookSpecificOutput",
    "NotificationHookSpecificOutput",
    "SubagentStartHookSpecificOutput",
    "PermissionRequestHookSpecificOutput",
    "SessionStartHookSpecificOutput",
    "SetupHookSpecificOutput",
    "ElicitationHookSpecificOutput",
    "ElicitationResultHookSpecificOutput",
    # Config types
    "ToolsPreset",
    "SystemPromptPreset",
    "SettingSource",
    "SdkBeta",
    "ThinkingConfig",
    "ThinkingConfigAdaptive",
    "ThinkingConfigEnabled",
    "ThinkingConfigDisabled",
    "SdkPluginConfig",
    "ConfigScope",
    "OutputFormatType",
    "OutputFormat",
    "JsonSchemaOutputFormat",
    "ToolConfig",
    "ToolAnnotations",
    "Settings",
    # Agent
    "AgentDefinition",
    # Session
    "SDKSessionInfo",
    "SDKSessionOptions",
    "ListSessionsOptions",
    "GetSessionMessagesOptions",
    "SessionMessage",
    # Sandbox
    "SandboxSettings",
    "SandboxNetworkConfig",
    "SandboxIgnoreViolations",
    "SandboxFilesystemConfig",
    # Elicitation
    "ElicitationRequest",
    "ElicitationResult",
    "OnElicitation",
    # Prompt
    "PromptRequest",
    "PromptRequestOption",
    "PromptResponse",
    # Exit / Abort
    "ExitReason",
    "EXIT_REASONS",
    "AbortError",
    # Status
    "ApiKeySource",
    "FastModeState",
    "SDKStatus",
    # Model / Account
    "ModelInfo",
    "ModelUsage",
    "NonNullableUsage",
    "AccountInfo",
    "AgentInfo",
    "SlashCommand",
    "RewindFilesResult",
    "SpawnOptions",
    "CallToolResult",
    # External stubs
    "BetaUsage",
    "BetaMessage",
    "BetaRawMessageStreamEvent",
    "MessageParam",
    # SDK message types
    "SDKMessage",
    "SDKPermissionDenial",
    "SDKAssistantMessage",
    "SDKUserMessage",
    "SDKUserMessageReplay",
    "SDKResultSuccess",
    "SDKResultError",
    "SDKResultMessage",
    "SDKSystemMessage",
    "SDKPartialAssistantMessage",
    "SDKCompactBoundaryMessage",
    "SDKStatusMessage",
    "SDKLocalCommandOutputMessage",
    "SDKHookStartedMessage",
    "SDKHookProgressMessage",
    "SDKHookResponseMessage",
    "SDKToolProgressMessage",
    "SDKAuthStatusMessage",
    "SDKTaskNotificationMessage",
    "SDKTaskStartedMessage",
    "SDKTaskProgressMessage",
    "SDKFilesPersistedEvent",
    "SDKToolUseSummaryMessage",
    "SDKRateLimitInfo",
    "SDKRateLimitEvent",
    "SDKElicitationCompleteMessage",
    "SDKPromptSuggestionMessage",
    "SDKControlInitializeResponse",
    # Errors
    "ClaudeSDKError",
    "CLINotFoundError",
    "CLIConnectionError",
    "ProcessError",
    "CLIJSONDecodeError",
    "MessageParseError",
    # ── Multi-provider types ────────────────────────────────────────────
    # Core types
    "StreamChunk",
    "TextChunk",
    "ToolCallChunk",
    "ToolResultChunk",
    "HandoffChunk",
    "ErrorChunk",
    "DoneChunk",
    "UsageInfo",
    "ToolDef",
    "AgentDef",
    "AgentMcpServerConfig",
    "RunConfig",
    "AgentRun",
    "Middleware",
    "MiddlewareContext",
    "ProviderBackend",
    "BuiltinProvider",
    "Provider",
    # Provider system
    "create_provider",
    "register_provider",
    "clear_providers",
    "ProviderFactory",
    # Middleware
    "apply_middleware",
    "define_middleware",
    "filter",
    "FilterOptions",
    "guardrails",
    "GuardrailsOptions",
    "hooks",
    "HooksOptions",
    "logging",
    "LoggingOptions",
    "text_collector",
    "TextCollectorHandle",
    "TextCollectorOptions",
    "timing",
    "TimingHandle",
    "TimingInfo",
    "TimingOptions",
    "usage_tracker",
    "UsageStats",
    "UsageTrackerHandle",
    "UsageTrackerOptions",
    # Session (multi-turn)
    "Session",
    "SessionConfig",
    "SessionStore",
    "MemoryStore",
    "create_session",
    "ConversationMessage",
    # Runner (deprecated)
    "run",
    "run_to_completion",
    # Deprecated helpers
    "define_agent",
    "define_tool",
    # Utils
    "extract_json",
    "handoff_tool_name",
    "parse_handoff",
    "build_tool_map",
]
