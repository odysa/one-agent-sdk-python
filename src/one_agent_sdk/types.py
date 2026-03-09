"""All type definitions for the One Agent SDK.

Direct port of claude-agent-sdk-python types using the same dataclasses and
TypedDicts so that the public API is a drop-in replacement.
"""

from __future__ import annotations

import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar

from typing_extensions import NotRequired, TypedDict

# ---------------------------------------------------------------------------
# Generic type variable for SdkMcpTool
# ---------------------------------------------------------------------------

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Content blocks
# ---------------------------------------------------------------------------


@dataclass
class TextBlock:
    text: str


@dataclass
class ThinkingBlock:
    thinking: str
    signature: str


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResultBlock:
    tool_use_id: str
    content: str | list[dict[str, Any]] | None = None
    is_error: bool | None = None


ContentBlock = TextBlock | ThinkingBlock | ToolUseBlock | ToolResultBlock

# ---------------------------------------------------------------------------
# Assistant message error
# ---------------------------------------------------------------------------

AssistantMessageError = Literal[
    "authentication_failed",
    "billing_error",
    "rate_limit",
    "invalid_request",
    "server_error",
    "unknown",
    "max_output_tokens",
]

# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------


@dataclass
class UserMessage:
    content: str | list[ContentBlock]
    uuid: str | None = None
    parent_tool_use_id: str | None = None
    tool_use_result: dict[str, Any] | None = None


@dataclass
class AssistantMessage:
    content: list[ContentBlock]
    model: str
    parent_tool_use_id: str | None = None
    error: AssistantMessageError | None = None


@dataclass
class SystemMessage:
    subtype: str
    data: dict[str, Any]


@dataclass
class ResultMessage:
    subtype: str
    duration_ms: int
    duration_api_ms: int
    is_error: bool
    num_turns: int
    session_id: str
    total_cost_usd: float | None = None
    usage: dict[str, Any] | None = None
    result: str | None = None
    stop_reason: str | None = None
    structured_output: Any = None


@dataclass
class StreamEvent:
    uuid: str
    session_id: str
    event: dict[str, Any]
    parent_tool_use_id: str | None = None


# ---------------------------------------------------------------------------
# Task messages (subclasses of SystemMessage)
# ---------------------------------------------------------------------------


class TaskUsage(TypedDict):
    total_tokens: int
    tool_uses: int
    duration_ms: int


TaskNotificationStatus = Literal["completed", "failed", "stopped"]


@dataclass
class TaskStartedMessage(SystemMessage):
    task_id: str = ""
    description: str = ""
    uuid: str = ""
    session_id: str = ""
    tool_use_id: str | None = None
    task_type: str | None = None


@dataclass
class TaskProgressMessage(SystemMessage):
    task_id: str = ""
    description: str = ""
    usage: TaskUsage = field(default_factory=lambda: TaskUsage(total_tokens=0, tool_uses=0, duration_ms=0))  # type: ignore[typeddict-item]
    uuid: str = ""
    session_id: str = ""
    tool_use_id: str | None = None
    last_tool_name: str | None = None


@dataclass
class TaskNotificationMessage(SystemMessage):
    task_id: str = ""
    status: TaskNotificationStatus = "completed"
    output_file: str = ""
    summary: str = ""
    uuid: str = ""
    session_id: str = ""
    tool_use_id: str | None = None
    usage: TaskUsage | None = None


# ---------------------------------------------------------------------------
# Message union
# ---------------------------------------------------------------------------

Message = (
    UserMessage
    | AssistantMessage
    | SystemMessage
    | ResultMessage
    | StreamEvent
)

# ---------------------------------------------------------------------------
# MCP server config types
# ---------------------------------------------------------------------------


class McpStdioServerConfig(TypedDict):
    type: NotRequired[Literal["stdio"]]
    command: str
    args: NotRequired[list[str]]
    env: NotRequired[dict[str, str]]


class McpSSEServerConfig(TypedDict):
    type: Literal["sse"]
    url: str
    headers: NotRequired[dict[str, str]]


class McpHttpServerConfig(TypedDict):
    type: Literal["http"]
    url: str
    headers: NotRequired[dict[str, str]]


class McpSdkServerConfig(TypedDict):
    type: Literal["sdk"]
    name: str
    instance: Any


McpServerConfig = (
    McpStdioServerConfig
    | McpSSEServerConfig
    | McpHttpServerConfig
    | McpSdkServerConfig
)

# ---------------------------------------------------------------------------
# MCP server status
# ---------------------------------------------------------------------------

McpServerConnectionStatus = Literal[
    "connected", "failed", "needs-auth", "pending", "disabled"
]


class McpServerInfo(TypedDict):
    name: str
    version: str


class McpToolInfo(TypedDict):
    name: str
    description: NotRequired[str]
    annotations: NotRequired[dict[str, Any]]


class McpServerStatus(TypedDict):
    name: str
    status: McpServerConnectionStatus
    serverInfo: NotRequired[McpServerInfo]
    error: NotRequired[str]
    config: NotRequired[dict[str, Any]]
    scope: NotRequired[str]
    tools: NotRequired[list[McpToolInfo]]


# ---------------------------------------------------------------------------
# SdkMcpTool
# ---------------------------------------------------------------------------


@dataclass
class SdkMcpTool(Generic[T]):
    name: str
    description: str
    input_schema: type[T] | dict[str, Any]
    handler: Callable[[T], Awaitable[dict[str, Any]]]
    annotations: Any | None = None  # mcp.types.ToolAnnotations


# ---------------------------------------------------------------------------
# Permission types
# ---------------------------------------------------------------------------

PermissionMode = Literal[
    "default",
    "acceptEdits",
    "plan",
    "bypassPermissions",
    "dontAsk",
]


@dataclass
class PermissionRuleValue:
    tool_name: str
    rule_content: str | None = None


@dataclass
class PermissionUpdate:
    type: Literal[
        "addRules",
        "replaceRules",
        "removeRules",
        "setMode",
        "addDirectories",
        "removeDirectories",
    ]
    rules: list[PermissionRuleValue] | None = None
    behavior: Literal["allow", "deny", "ask"] | None = None
    mode: PermissionMode | None = None
    directories: list[str] | None = None
    destination: (
        Literal[
            "userSettings",
            "projectSettings",
            "localSettings",
            "session",
        ]
        | None
    ) = None


@dataclass
class ToolPermissionContext:
    signal: Any | None = None
    suggestions: list[PermissionUpdate] = field(default_factory=list)


@dataclass
class PermissionResultAllow:
    behavior: Literal["allow"] = "allow"
    updated_input: dict[str, Any] | None = None
    updated_permissions: list[PermissionUpdate] | None = None


@dataclass
class PermissionResultDeny:
    behavior: Literal["deny"] = "deny"
    message: str = ""
    interrupt: bool = False


PermissionResult = PermissionResultAllow | PermissionResultDeny

CanUseTool = Callable[
    [str, dict[str, Any], ToolPermissionContext],
    Awaitable[PermissionResult],
]

# ---------------------------------------------------------------------------
# Presets & configs
# ---------------------------------------------------------------------------


class ToolsPreset(TypedDict):
    type: Literal["preset"]
    preset: Literal["claude_code"]


class SystemPromptPreset(TypedDict):
    type: Literal["preset"]
    preset: Literal["claude_code"]
    append: NotRequired[str]


SettingSource = Literal["user", "project", "local"]

SdkBeta = Literal["context-1m-2025-08-07"]


class ThinkingConfigAdaptive(TypedDict):
    type: Literal["adaptive"]


class ThinkingConfigEnabled(TypedDict):
    type: Literal["enabled"]
    budget_tokens: int


class ThinkingConfigDisabled(TypedDict):
    type: Literal["disabled"]


ThinkingConfig = (
    ThinkingConfigAdaptive | ThinkingConfigEnabled | ThinkingConfigDisabled
)


class SdkPluginConfig(TypedDict):
    type: Literal["local"]
    path: str


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------


@dataclass
class AgentDefinition:
    description: str
    prompt: str
    tools: list[str] | None = None
    disallowed_tools: list[str] | None = None
    model: Literal["sonnet", "opus", "haiku", "inherit"] | None = None
    mcp_servers: list[str | dict[str, Any]] | None = None
    critical_system_reminder_EXPERIMENTAL: str | None = None
    skills: list[str] | None = None
    max_turns: int | None = None


# ---------------------------------------------------------------------------
# Sandbox
# ---------------------------------------------------------------------------


class SandboxNetworkConfig(TypedDict, total=False):
    allowLocalBinding: bool
    allowUnixSockets: list[str]
    allowAllUnixSockets: bool
    httpProxyPort: int
    socksProxyPort: int


class SandboxIgnoreViolations(TypedDict, total=False):
    file: list[str]
    network: list[str]


class SandboxSettings(TypedDict, total=False):
    enabled: bool
    autoAllowBashIfSandboxed: bool
    excludedCommands: list[str]
    allowUnsandboxedCommands: bool
    network: SandboxNetworkConfig
    ignoreViolations: SandboxIgnoreViolations
    enableWeakerNestedSandbox: bool


# ---------------------------------------------------------------------------
# Hook types
# ---------------------------------------------------------------------------

HookEvent = Literal[
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "UserPromptSubmit",
    "Stop",
    "SubagentStop",
    "PreCompact",
    "Notification",
    "SubagentStart",
    "PermissionRequest",
    "SessionStart",
    "SessionEnd",
    "Setup",
    "TeammateIdle",
    "TaskCompleted",
    "Elicitation",
    "ElicitationResult",
    "ConfigChange",
    "WorktreeCreate",
    "WorktreeRemove",
    "InstructionsLoaded",
]

HOOK_EVENTS: tuple[str, ...] = (
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "Notification",
    "UserPromptSubmit",
    "SessionStart",
    "SessionEnd",
    "Stop",
    "SubagentStart",
    "SubagentStop",
    "PreCompact",
    "PermissionRequest",
    "Setup",
    "TeammateIdle",
    "TaskCompleted",
    "Elicitation",
    "ElicitationResult",
    "ConfigChange",
    "WorktreeCreate",
    "WorktreeRemove",
    "InstructionsLoaded",
)


class HookContext(TypedDict):
    signal: Any | None


class BaseHookInput(TypedDict):
    session_id: str
    transcript_path: str
    cwd: str
    permission_mode: NotRequired[str]


class PreToolUseHookInput(BaseHookInput):
    hook_event_name: Literal["PreToolUse"]
    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str
    agent_id: NotRequired[str]
    agent_type: NotRequired[str]


class PostToolUseHookInput(BaseHookInput):
    hook_event_name: Literal["PostToolUse"]
    tool_name: str
    tool_input: dict[str, Any]
    tool_response: Any
    tool_use_id: str
    agent_id: NotRequired[str]
    agent_type: NotRequired[str]


class PostToolUseFailureHookInput(BaseHookInput):
    hook_event_name: Literal["PostToolUseFailure"]
    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str
    error: str
    is_interrupt: NotRequired[bool]
    agent_id: NotRequired[str]
    agent_type: NotRequired[str]


class UserPromptSubmitHookInput(BaseHookInput):
    hook_event_name: Literal["UserPromptSubmit"]
    prompt: str


class StopHookInput(BaseHookInput):
    hook_event_name: Literal["Stop"]
    stop_hook_active: bool


class SubagentStopHookInput(BaseHookInput):
    hook_event_name: Literal["SubagentStop"]
    stop_hook_active: bool
    agent_id: str
    agent_transcript_path: str
    agent_type: str


class PreCompactHookInput(BaseHookInput):
    hook_event_name: Literal["PreCompact"]
    trigger: Literal["manual", "auto"]
    custom_instructions: str | None


class NotificationHookInput(BaseHookInput):
    hook_event_name: Literal["Notification"]
    message: str
    title: NotRequired[str]
    notification_type: str


class SubagentStartHookInput(BaseHookInput):
    hook_event_name: Literal["SubagentStart"]
    agent_id: str
    agent_type: str


class PermissionRequestHookInput(BaseHookInput):
    hook_event_name: Literal["PermissionRequest"]
    tool_name: str
    tool_input: dict[str, Any]
    permission_suggestions: NotRequired[list[Any]]


HookInput = (
    PreToolUseHookInput
    | PostToolUseHookInput
    | PostToolUseFailureHookInput
    | UserPromptSubmitHookInput
    | StopHookInput
    | SubagentStopHookInput
    | PreCompactHookInput
    | NotificationHookInput
    | SubagentStartHookInput
    | PermissionRequestHookInput
)

# ---------------------------------------------------------------------------
# Hook outputs
# ---------------------------------------------------------------------------


class PreToolUseHookSpecificOutput(TypedDict):
    hookEventName: Literal["PreToolUse"]
    permissionDecision: NotRequired[Literal["allow", "deny", "ask"]]
    permissionDecisionReason: NotRequired[str]
    updatedInput: NotRequired[dict[str, Any]]
    additionalContext: NotRequired[str]


class PostToolUseHookSpecificOutput(TypedDict):
    hookEventName: Literal["PostToolUse"]
    additionalContext: NotRequired[str]
    updatedMCPToolOutput: NotRequired[Any]


class PostToolUseFailureHookSpecificOutput(TypedDict):
    hookEventName: Literal["PostToolUseFailure"]
    additionalContext: NotRequired[str]


class UserPromptSubmitHookSpecificOutput(TypedDict):
    hookEventName: Literal["UserPromptSubmit"]
    additionalContext: NotRequired[str]


class NotificationHookSpecificOutput(TypedDict):
    hookEventName: Literal["Notification"]
    additionalContext: NotRequired[str]


class SubagentStartHookSpecificOutput(TypedDict):
    hookEventName: Literal["SubagentStart"]
    additionalContext: NotRequired[str]


class PermissionRequestHookSpecificOutput(TypedDict):
    hookEventName: Literal["PermissionRequest"]
    decision: dict[str, Any]


HookSpecificOutput = (
    PreToolUseHookSpecificOutput
    | PostToolUseHookSpecificOutput
    | PostToolUseFailureHookSpecificOutput
    | UserPromptSubmitHookSpecificOutput
    | NotificationHookSpecificOutput
    | SubagentStartHookSpecificOutput
    | PermissionRequestHookSpecificOutput
)


class SyncHookJSONOutput(TypedDict):
    continue_: NotRequired[bool]
    suppressOutput: NotRequired[bool]
    stopReason: NotRequired[str]
    decision: NotRequired[Literal["block"]]
    systemMessage: NotRequired[str]
    reason: NotRequired[str]
    hookSpecificOutput: NotRequired[HookSpecificOutput]


class AsyncHookJSONOutput(TypedDict):
    async_: Literal[True]
    asyncTimeout: NotRequired[int]


HookJSONOutput = AsyncHookJSONOutput | SyncHookJSONOutput

HookCallback = Callable[
    [HookInput, str | None, HookContext],
    Awaitable[HookJSONOutput],
]


@dataclass
class HookMatcher:
    matcher: str | None = None
    hooks: list[HookCallback] = field(default_factory=list)
    timeout: float | None = None


# ---------------------------------------------------------------------------
# Session types
# ---------------------------------------------------------------------------


@dataclass
class SDKSessionInfo:
    session_id: str
    summary: str
    last_modified: int
    file_size: int
    custom_title: str | None = None
    first_prompt: str | None = None
    git_branch: str | None = None
    cwd: str | None = None


@dataclass
class SessionMessage:
    type: Literal["user", "assistant"]
    uuid: str
    session_id: str
    message: Any
    parent_tool_use_id: None = None


# ---------------------------------------------------------------------------
# ClaudeAgentOptions
# ---------------------------------------------------------------------------


@dataclass
class ClaudeAgentOptions:
    tools: list[str] | ToolsPreset | None = None
    allowed_tools: list[str] = field(default_factory=list)
    system_prompt: str | SystemPromptPreset | None = None
    mcp_servers: dict[str, McpServerConfig] | str | Path = field(
        default_factory=dict
    )
    permission_mode: PermissionMode | None = None
    continue_conversation: bool = False
    resume: str | None = None
    max_turns: int | None = None
    max_budget_usd: float | None = None
    disallowed_tools: list[str] = field(default_factory=list)
    model: str | None = None
    fallback_model: str | None = None
    betas: list[SdkBeta] = field(default_factory=list)
    output_format: dict[str, Any] | None = None
    permission_prompt_tool_name: str | None = None
    cwd: str | Path | None = None
    cli_path: str | Path | None = None
    settings: str | None = None
    add_dirs: list[str | Path] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    extra_args: dict[str, str | None] = field(default_factory=dict)
    max_buffer_size: int | None = None
    debug_stderr: Any = sys.stderr  # Deprecated
    stderr: Callable[[str], None] | None = None
    can_use_tool: CanUseTool | None = None
    hooks: dict[HookEvent, list[HookMatcher]] | None = None
    user: str | None = None
    include_partial_messages: bool = False
    fork_session: bool = False
    agents: dict[str, AgentDefinition] | None = None
    setting_sources: list[SettingSource] | None = None
    sandbox: SandboxSettings | None = None
    plugins: list[SdkPluginConfig] = field(default_factory=list)
    max_thinking_tokens: int | None = None  # Deprecated: use thinking instead
    thinking: ThinkingConfig | None = None
    effort: Literal["low", "medium", "high", "max"] | None = None
    enable_file_checkpointing: bool = False
    persist_session: bool = False
    on_elicitation: Any | None = None
    tool_config: dict[str, Any] | None = None
    session_id: str | None = None
    resume_session_at: str | None = None
    prompt_suggestions: bool = False
    debug: bool = False
    debug_file: str | None = None
    strict_mcp_config: bool = False
    allow_dangerously_skip_permissions: bool = False
    executable: Literal["bun", "deno", "node"] | None = None
    executable_args: list[str] = field(default_factory=list)
    spawn_claude_code_process: Any | None = None
    # Provider routing (one-agent-sdk extension)
    provider: str | None = None


# ---------------------------------------------------------------------------
# Elicitation types
# ---------------------------------------------------------------------------


class ElicitationRequest(TypedDict):
    server_name: str
    message: str
    mode: NotRequired[Literal["form", "url"]]
    url: NotRequired[str]
    elicitation_id: NotRequired[str]
    requested_schema: NotRequired[dict[str, Any]]


ElicitationResult = dict[str, Any]

OnElicitation = Callable[
    [ElicitationRequest, Any],
    Awaitable[ElicitationResult],
]


# ---------------------------------------------------------------------------
# New hook input types
# ---------------------------------------------------------------------------


class SessionStartHookInput(BaseHookInput):
    hook_event_name: Literal["SessionStart"]


class SessionEndHookInput(BaseHookInput):
    hook_event_name: Literal["SessionEnd"]


class SetupHookInput(BaseHookInput):
    hook_event_name: Literal["Setup"]


class TeammateIdleHookInput(BaseHookInput):
    hook_event_name: Literal["TeammateIdle"]


class TaskCompletedHookInput(BaseHookInput):
    hook_event_name: Literal["TaskCompleted"]


class ElicitationHookInput(BaseHookInput):
    hook_event_name: Literal["Elicitation"]


class ElicitationResultHookInput(BaseHookInput):
    hook_event_name: Literal["ElicitationResult"]


class ConfigChangeHookInput(BaseHookInput):
    hook_event_name: Literal["ConfigChange"]


class InstructionsLoadedHookInput(BaseHookInput):
    hook_event_name: Literal["InstructionsLoaded"]


class WorktreeCreateHookInput(BaseHookInput):
    hook_event_name: Literal["WorktreeCreate"]


class WorktreeRemoveHookInput(BaseHookInput):
    hook_event_name: Literal["WorktreeRemove"]


# New hook output types

class SessionStartHookSpecificOutput(TypedDict):
    hookEventName: Literal["SessionStart"]


class SetupHookSpecificOutput(TypedDict):
    hookEventName: Literal["Setup"]


class ElicitationHookSpecificOutput(TypedDict):
    hookEventName: Literal["Elicitation"]


class ElicitationResultHookSpecificOutput(TypedDict):
    hookEventName: Literal["ElicitationResult"]


# ---------------------------------------------------------------------------
# Exit reasons
# ---------------------------------------------------------------------------

ExitReason = Literal[
    "clear",
    "logout",
    "prompt_input_exit",
    "other",
    "bypass_permissions_disabled",
]

EXIT_REASONS: tuple[str, ...] = (
    "clear",
    "logout",
    "prompt_input_exit",
    "other",
    "bypass_permissions_disabled",
)


# ---------------------------------------------------------------------------
# AbortError
# ---------------------------------------------------------------------------


class AbortError(Exception):
    """Raised when an operation is aborted."""
    pass


# ---------------------------------------------------------------------------
# Additional SDK message type aliases
# ---------------------------------------------------------------------------

PermissionBehavior = Literal["allow", "deny", "ask"]

PermissionUpdateDestination = Literal[
    "userSettings",
    "projectSettings",
    "localSettings",
    "session",
    "cliArg",
]

ApiKeySource = Literal["user", "project", "org", "temporary", "oauth"]
FastModeState = Literal["off", "cooldown", "on"]
SDKStatus = Literal["compacting"] | None
ConfigScope = Literal["local", "user", "project"]
OutputFormatType = Literal["json_schema"]


class PromptRequestOption(TypedDict):
    key: str
    label: str
    description: NotRequired[str]


class PromptRequest(TypedDict):
    prompt: str
    message: str
    options: list[PromptRequestOption]


class PromptResponse(TypedDict):
    prompt_response: str
    selected: str
