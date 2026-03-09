"""GitHub Copilot provider — uses the @github/copilot-sdk."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from ..types_core import (
    DoneChunk,
    ErrorChunk,
    HandoffChunk,
    ProviderBackend,
    RunConfig,
    StreamChunk,
    TextChunk,
    ToolCallChunk,
    ToolResultChunk,
    UsageInfo,
)
from ..utils.handoff import handoff_tool_name, parse_handoff


async def create_copilot_provider(config: RunConfig) -> ProviderBackend:
    """Create a GitHub Copilot provider backend.

    Requires the ``copilot-sdk`` package.
    """
    try:
        from copilot_sdk import CopilotClient, approve_all, define_tool
    except ImportError as exc:
        raise ImportError(
            "Copilot provider requires 'copilot-sdk' package: pip install copilot-sdk"
        ) from exc

    agent_tools = config.agent.tools or []
    opts = config.provider_options or {}

    tools = [
        define_tool(
            name=t.name,
            description=t.description,
            parameters=t.parameters,
            handler=t.handler,
        )
        for t in agent_tools
    ]

    current_agent = config.agent

    for target_name in config.agent.handoffs or []:
        target = (config.agents or {}).get(target_name)
        tools.append(
            define_tool(
                name=handoff_tool_name(target_name),
                description=target.description if target else f"Transfer to {target_name}",
                parameters={},
                handler=lambda: f"Transferred to {target_name}",
            )
        )

    client_options: dict[str, Any] = {}
    for key in ("cliPath", "cliUrl", "githubToken"):
        if opts.get(key):
            client_options[key] = opts[key]
    if opts.get("clientOptions"):
        client_options.update(opts["clientOptions"])

    client = CopilotClient(**client_options)
    await client.start()

    session_config: dict[str, Any] = {
        "streaming": True,
        "tools": tools,
        "onPermissionRequest": approve_all,
    }
    if config.agent.model:
        session_config["model"] = config.agent.model
    if opts.get("reasoningEffort"):
        session_config["reasoningEffort"] = opts["reasoningEffort"]
    if config.agent.prompt:
        session_config["systemMessage"] = {"content": config.agent.prompt}
    if config.work_dir:
        session_config["workDir"] = config.work_dir
    if opts.get("sessionOptions"):
        session_config.update(opts["sessionOptions"])

    session = await client.create_session(**session_config)

    class _CopilotProvider:
        async def _run_prompt(self, prompt: str) -> AsyncGenerator[StreamChunk, None]:
            nonlocal current_agent
            full_text = ""
            done = False
            queue: list[StreamChunk] = []
            event = asyncio.Event()
            usage: UsageInfo | None = None

            def push(chunk: StreamChunk) -> None:
                queue.append(chunk)
                event.set()

            unsubs: list[Any] = []

            unsubs.append(session.on("assistant.message_delta", lambda ev: _on_delta(ev, push)))
            unsubs.append(session.on("tool.execution_start", lambda ev: _on_tool_start(ev, push, current_agent, config)))
            unsubs.append(session.on("tool.execution_complete", lambda ev: _on_tool_complete(ev, push)))

            def on_usage(ev: Any) -> None:
                nonlocal usage
                data = getattr(ev, "data", {})
                if data.get("inputTokens") is not None:
                    usage = UsageInfo(
                        input_tokens=data["inputTokens"],
                        output_tokens=data.get("outputTokens", 0),
                    )

            unsubs.append(session.on("assistant.usage", on_usage))

            def on_error(ev: Any) -> None:
                nonlocal done
                data = getattr(ev, "data", {})
                push(ErrorChunk(error=data.get("message", "Unknown error")))
                push(DoneChunk(text=full_text, usage=usage))
                done = True

            unsubs.append(session.on("session.error", on_error))

            def on_idle(_ev: Any) -> None:
                nonlocal done
                push(DoneChunk(text=full_text, usage=usage))
                done = True

            unsubs.append(session.on("session.idle", on_idle))

            await session.send({"prompt": prompt})

            try:
                while not done or queue:
                    if queue:
                        chunk = queue.pop(0)
                        if isinstance(chunk, TextChunk):
                            full_text += chunk.text
                        yield chunk
                    elif not done:
                        event.clear()
                        await event.wait()
            finally:
                for unsub in unsubs:
                    if callable(unsub):
                        unsub()

        def run(self, prompt: str, cfg: RunConfig) -> AsyncGenerator[StreamChunk, None]:
            return self._run_prompt(prompt)

        def chat(self, message: str) -> AsyncGenerator[StreamChunk, None]:
            return self._run_prompt(message)

        async def close(self) -> None:
            try:
                await session.destroy()
            finally:
                await client.stop()

    return _CopilotProvider()  # type: ignore[return-value]


def _on_delta(ev: Any, push: Any) -> None:
    data = getattr(ev, "data", {})
    text = data.get("deltaContent", "")
    if text:
        push(TextChunk(text=text))


def _on_tool_start(ev: Any, push: Any, current_agent: Any, config: Any) -> None:
    data = getattr(ev, "data", {})
    name = data.get("toolName", "")
    push(ToolCallChunk(
        tool_name=name,
        tool_args=data.get("arguments", {}),
        tool_call_id=data.get("toolCallId", ""),
    ))
    handoff_target = parse_handoff(name)
    if handoff_target:
        target = (config.agents or {}).get(handoff_target)
        if target:
            push(HandoffChunk(from_agent=current_agent.name, to_agent=handoff_target))


def _on_tool_complete(ev: Any, push: Any) -> None:
    data = getattr(ev, "data", {})
    result = data.get("result", {}).get("content", "")
    push(ToolResultChunk(
        tool_call_id=data.get("toolCallId", ""),
        result=result if isinstance(result, str) else str(result),
    ))
