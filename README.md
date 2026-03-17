<div align="center">

# One Agent SDK for Python

[![PyPI version](https://img.shields.io/pypi/v/one-agent-sdk?style=flat-square&color=3775A9&label=PyPI)](https://pypi.org/project/one-agent-sdk/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](https://opensource.org/licenses/MIT)

**Drop-in replacement for `claude-agent-sdk-python` — same API, multiple providers.**

<br />

[Getting Started](#getting-started) · [Features](#features) · [Providers](#supported-providers) · [API Reference](#api-reference) · [Examples](#examples)

<br />

</div>

```python
from one_agent_sdk import query, tool, create_sdk_mcp_server, ClaudeAgentOptions

# Same API as claude-agent-sdk — swap provider with one option
async for msg in query(prompt="What's the weather?", options=ClaudeAgentOptions(provider="codex")):
    print(msg)
```

<br />

## The Problem

`claude-agent-sdk-python` has a great API — but it only works with Claude Code. If you want to use Codex, Kimi, or OpenAI, you need a completely different SDK.

## The Solution

One Agent SDK is a drop-in replacement that routes to any backend. Same `query()`, `tool()`, `create_sdk_mcp_server()` — just pass `options.provider` to switch:

```diff
  async for msg in query(
      prompt="Analyze this code",
-     options=ClaudeAgentOptions(system_prompt="You are helpful."),
+     options=ClaudeAgentOptions(system_prompt="You are helpful.", provider="codex"),
  ):
      print(msg)
```

Everything else stays the same: streaming, tools, message format — all of it.

<br />

## Supported Providers

### CLI Agent Providers

These wrap CLI agent SDKs — no API keys needed, agents run as local subprocesses using your existing CLI authentication.

| Provider | Backend | Notes |
| :------- | :------ | :---- |
| `claude-code` | Claude Code CLI | Default provider |
| `codex` | OpenAI Codex | Requires `openai` extra |
| `copilot` | GitHub Copilot | Requires `openai` extra |
| `kimi-cli` | Kimi CLI | Requires `openai` extra |

### API-Key Providers

These call LLM HTTP APIs directly with API keys — no CLI tooling required.

| Provider | Backend | Notes |
| :------- | :------ | :---- |
| `openai` | OpenAI API (GPT-4o, etc.) | Requires `openai` extra |
| `anthropic` | Anthropic API (Claude Sonnet, etc.) | Requires `anthropic` extra |
| `openrouter` | [OpenRouter](https://openrouter.ai/) (any model) | Requires `openai` extra |

All providers are **optional dependencies** — install only what you need. You can also [register custom providers](#custom-providers).

<br />

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- At least one provider: either a CLI agent installed and authenticated, or an API key

### Install

```bash
# With uv (recommended)
uv add one-agent-sdk

# With pip
pip install one-agent-sdk
```

Install provider extras as needed:

```bash
# For OpenAI, Codex, Copilot, Kimi, or OpenRouter providers
uv add "one-agent-sdk[openai]"

# For Anthropic API provider
uv add "one-agent-sdk[anthropic]"

# Install all optional providers
uv add "one-agent-sdk[all]"
```

### Quick Start

```python
import asyncio
from one_agent_sdk import query, tool, create_sdk_mcp_server, ClaudeAgentOptions


@tool("get_weather", "Get the current weather for a city", {"city": str})
async def get_weather(args):
    city = args["city"]
    return {
        "content": [
            {"type": "text", "text": f'{{"city": "{city}", "temperature": 72, "condition": "sunny"}}'}
        ]
    }


server = create_sdk_mcp_server("tools", tools=[get_weather])


async def main():
    opts = ClaudeAgentOptions(
        system_prompt="You are a helpful assistant. Use the weather tool when asked about weather.",
        mcp_servers={"tools": server},
        allowed_tools=["mcp__tools__get_weather"],
    )

    async for msg in query(prompt="What's the weather in San Francisco?", options=opts):
        if msg.type == "assistant" and hasattr(msg, "message"):
            for block in msg.message.get("content", []):
                if "text" in block:
                    print(block["text"], end="")
    print()


asyncio.run(main())
```

> **Tip:** To switch providers, add `provider="codex"`, `provider="openai"`, etc. to `ClaudeAgentOptions`. Defaults to `"claude-code"`.

<br />

## Features

### Multi-Provider Support

Same code, different backend — just change the provider:

```python
from one_agent_sdk import query, ClaudeAgentOptions

# Use Claude (default)
async for msg in query(prompt="Explain this code"):
    ...

# Use Codex
async for msg in query(prompt="Explain this code", options=ClaudeAgentOptions(provider="codex")):
    ...

# Use OpenAI API directly
async for msg in query(prompt="Explain this code", options=ClaudeAgentOptions(provider="openai")):
    ...

# Use Anthropic API directly
async for msg in query(prompt="Explain this code", options=ClaudeAgentOptions(provider="anthropic")):
    ...

# Use any model via OpenRouter
async for msg in query(
    prompt="Explain this code",
    options=ClaudeAgentOptions(provider="openrouter", model="anthropic/claude-sonnet-4"),
):
    ...
```

The output stream always emits the same message format, regardless of provider.

### Streaming Primitives

The multi-provider layer uses a unified `StreamChunk` type:

```python
from one_agent_sdk import TextChunk, ToolCallChunk, ToolResultChunk, DoneChunk, ErrorChunk, HandoffChunk
```

| Chunk Type | Description |
| :--------- | :---------- |
| `TextChunk` | Text content from the model |
| `ToolCallChunk` | Model requesting a tool call |
| `ToolResultChunk` | Result returned from a tool |
| `HandoffChunk` | Multi-agent handoff signal |
| `ErrorChunk` | Error during generation |
| `DoneChunk` | Stream complete |

### Tools

Define tools with the `@tool` decorator:

```python
from one_agent_sdk import tool

@tool("calculate", "Perform arithmetic", {"expression": str})
async def calculate(args):
    result = eval(args["expression"])  # simplified
    return {"content": [{"type": "text", "text": str(result)}]}
```

### MCP Servers

Create in-process MCP servers for tool integration:

```python
from one_agent_sdk import create_sdk_mcp_server, ClaudeAgentOptions

server = create_sdk_mcp_server("my-tools", tools=[calculate])
opts = ClaudeAgentOptions(
    mcp_servers={"my-tools": server},
    allowed_tools=["mcp__my-tools__calculate"],
)
```

### Custom Providers

Register your own provider backend:

```python
from one_agent_sdk import register_provider, query, ClaudeAgentOptions
from one_agent_sdk.types_core import ProviderBackend, RunConfig, TextChunk, DoneChunk


class MyProvider(ProviderBackend):
    async def run(self, prompt, config):
        yield TextChunk(type="text", text="Hello from my provider!")
        yield DoneChunk(type="done")

    async def chat(self, messages, config):
        yield TextChunk(type="text", text="Response")
        yield DoneChunk(type="done")

    async def close(self):
        pass


register_provider("my-llm", lambda config: MyProvider())

async for msg in query(prompt="Hi", options=ClaudeAgentOptions(provider="my-llm")):
    print(msg)
```

### Middleware

Compose middleware for logging, usage tracking, timing, and more:

```python
from one_agent_sdk import (
    apply_middleware,
    logging,
    usage_tracker,
    timing,
    text_collector,
    hooks,
    guardrails,
    filter,
)

# Debug logging
stream = apply_middleware(original_stream, [logging()])

# Track token usage
tracker = usage_tracker()
stream = apply_middleware(original_stream, [tracker.middleware])
# After stream completes:
print(tracker.handle.stats)

# Measure timing (TTFC, TTFT, duration)
timer = timing()
stream = apply_middleware(original_stream, [timer.middleware])

# Collect all text output
collector = text_collector()
stream = apply_middleware(original_stream, [collector.middleware])
# After stream: collector.handle.text

# Content guardrails
stream = apply_middleware(original_stream, [guardrails(blocked_keywords=["secret"])])

# Filter chunk types
stream = apply_middleware(original_stream, [filter(include=["text", "done"])])
```

### Sessions

Multi-turn conversations with persistent history:

```python
from one_agent_sdk import create_session, MemoryStore

store = MemoryStore()
session = create_session(store=store)

# First turn
async for chunk in session.run("What is Python?"):
    print(chunk)

# Second turn (has context from first)
async for chunk in session.run("What about its type system?"):
    print(chunk)
```

### Client API

For more control, use `ClaudeSDKClient`:

```python
from one_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async with ClaudeSDKClient(ClaudeAgentOptions(model="claude-sonnet-4-20250514")) as client:
    async for msg in client.process_query("Hello"):
        print(msg)
```

### v2 Unstable APIs

Multi-turn session management (experimental):

```python
from one_agent_sdk import unstable_v2_create_session, unstable_v2_prompt

# One-shot prompt
result = await unstable_v2_prompt("What is 2+2?", {"model": "claude-sonnet-4-20250514"})

# Multi-turn session
async with await unstable_v2_create_session({"model": "claude-sonnet-4-20250514"}) as session:
    await session.send("Hello")
    async for msg in session.stream():
        print(msg)
```

<br />

## How It Works

```
query(prompt, options)
        |
        v
  options.provider?
        |
   ┌────┼────────────────────────────────────────────┐
   v    v         v          v        v       v       v
claude codex   copilot   kimi-cli  openai  anthropic  openrouter
 -code                                                 |
   |    |         |          |        |       |        |
   v    v         v          v        v       v        v
                    SDKMessage Stream
```

- **`claude-code`** (default) — delegates directly to the Claude Code CLI. Full fidelity, zero overhead.
- **CLI providers** (`codex`, `copilot`, `kimi-cli`) — wraps CLI agent SDKs, adapts output to SDK message format.
- **API providers** (`openai`, `anthropic`, `openrouter`) — calls LLM APIs directly with API keys, manages multi-turn tool loops internally.

> Provider dependencies are lazily imported at runtime — unused providers are never loaded.

<br />

## API Reference

### Core Functions

| Function | Description |
| :------- | :---------- |
| `query(prompt, options, transport)` | Stream messages from any provider |
| `tool(name, description, schema)` | Decorator for defining MCP tools |
| `create_sdk_mcp_server(name, tools)` | Create an in-process MCP server |
| `list_sessions()` | List existing Claude Code sessions |
| `get_session_messages(session_id)` | Retrieve messages from a session |

### Provider System

| Function | Description |
| :------- | :---------- |
| `create_provider(config)` | Create a provider backend from config |
| `register_provider(name, factory)` | Register a custom provider |
| `clear_providers()` | Reset the provider registry |

### Middleware

| Function | Description |
| :------- | :---------- |
| `apply_middleware(stream, middlewares)` | Compose middleware over a stream |
| `define_middleware(fn)` | Create a custom middleware |
| `logging()` | Debug logging middleware |
| `usage_tracker()` | Token usage aggregation |
| `timing()` | TTFC/TTFT/duration measurement |
| `text_collector()` | Accumulate text output |
| `hooks(options)` | Per-chunk-type callbacks |
| `guardrails(options)` | Content filtering |
| `filter(options)` | Include/exclude chunk types |

### Session

| Function | Description |
| :------- | :---------- |
| `create_session(store, config)` | Create a multi-turn session |
| `MemoryStore()` | In-memory session store |

### Options

`ClaudeAgentOptions` supports all `claude-agent-sdk` options plus:

| Option | Type | Description |
| :----- | :--- | :---------- |
| `provider` | `str` | Route to a different backend (default: `"claude-code"`) |
| `model` | `str` | Model to use |
| `system_prompt` | `str` | System prompt |
| `max_turns` | `int` | Maximum conversation turns |
| `permission_mode` | `str` | `"default"`, `"acceptEdits"`, `"plan"`, `"bypassPermissions"`, `"dontAsk"` |
| `allowed_tools` | `list[str]` | Tools the agent can use |
| `disallowed_tools` | `list[str]` | Tools the agent cannot use |
| `mcp_servers` | `dict` | MCP server configurations |
| `cwd` | `Path` | Working directory |
| `env` | `dict` | Environment variables |

See [types.py](src/one_agent_sdk/types.py) for the full list.

<br />

## Legacy API (Deprecated)

The following functions are exported and will be removed in v0.2:

| Function | Replacement |
| :------- | :---------- |
| `run(prompt, config)` | `query(prompt=..., options=...)` |
| `run_to_completion(prompt, config)` | `query()` + collect results |
| `define_agent(...)` | Use `AgentDef` directly |
| `define_tool(...)` | Use `@tool()` decorator |

<br />

## TypeScript SDK

Looking for the TypeScript version? See [one-agent-sdk](https://github.com/odysa/one-agent-sdk) on npm.

<br />

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

<br />

## License

MIT
