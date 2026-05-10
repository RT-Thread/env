"""Model API adapter and model configuration."""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import AsyncGenerator
from typing import Any

from eagent.core.errors import PromptTooLongError, classify_error, with_retry
from eagent.core.types import (
    Message,
    ModelConfig,
    StreamEvent,
    SystemPromptBlock,
    TextBlock,
    ThinkingBlock,
    TokenUsage,
    Tool,
    ToolUseBlock,
)

try:  # pragma: no cover - import availability depends on runtime environment
    from anthropic import Anthropic
except Exception:  # pragma: no cover
    Anthropic = None  # type: ignore[assignment]

MODEL_CONFIGS: dict[str, ModelConfig] = {
    "claude-sonnet-4-20250514": ModelConfig(
        model="claude-sonnet-4-20250514",
        context_window=200_000,
        max_output_tokens=16_384,
        supports_thinking=True,
        supports_caching=True,
        price_per_input_token=3 / 1_000_000,
        price_per_output_token=15 / 1_000_000,
        price_per_cache_read=0.3 / 1_000_000,
        price_per_cache_write=3.75 / 1_000_000,
    ),
    "claude-opus-4-20250514": ModelConfig(
        model="claude-opus-4-20250514",
        context_window=200_000,
        max_output_tokens=16_384,
        supports_thinking=True,
        supports_caching=True,
        price_per_input_token=15 / 1_000_000,
        price_per_output_token=75 / 1_000_000,
        price_per_cache_read=1.5 / 1_000_000,
        price_per_cache_write=18.75 / 1_000_000,
    ),
    "claude-haiku-4-5-20251001": ModelConfig(
        model="claude-haiku-4-5-20251001",
        context_window=200_000,
        max_output_tokens=16_384,
        supports_thinking=False,
        supports_caching=True,
        price_per_input_token=0.8 / 1_000_000,
        price_per_output_token=4 / 1_000_000,
        price_per_cache_read=0.08 / 1_000_000,
        price_per_cache_write=1 / 1_000_000,
    ),
}
MODEL_CONFIGS["sonnet"] = MODEL_CONFIGS["claude-sonnet-4-20250514"]
MODEL_CONFIGS["opus"] = MODEL_CONFIGS["claude-opus-4-20250514"]
MODEL_CONFIGS["haiku"] = MODEL_CONFIGS["claude-haiku-4-5-20251001"]

_last_usage = TokenUsage()


def get_last_usage() -> TokenUsage:
    return TokenUsage(
        input_tokens=_last_usage.input_tokens,
        output_tokens=_last_usage.output_tokens,
        cache_read_tokens=_last_usage.cache_read_tokens,
        cache_creation_tokens=_last_usage.cache_creation_tokens,
    )


def set_last_usage(usage: TokenUsage) -> None:
    global _last_usage
    _last_usage = usage


def get_model_config(model: str) -> ModelConfig:
    if model in MODEL_CONFIGS:
        return MODEL_CONFIGS[model]
    for key, cfg in MODEL_CONFIGS.items():
        if key in model or model in key:
            return cfg
    base = MODEL_CONFIGS["sonnet"]
    return ModelConfig(
        model=model,
        context_window=base.context_window,
        max_output_tokens=base.max_output_tokens,
        supports_thinking=base.supports_thinking,
        supports_caching=base.supports_caching,
        price_per_input_token=base.price_per_input_token,
        price_per_output_token=base.price_per_output_token,
        price_per_cache_read=base.price_per_cache_read,
        price_per_cache_write=base.price_per_cache_write,
    )


def _message_to_api(message: Message) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    for block in message.content:
        if block.type == "text":
            content.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            content.append(
                {
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                }
            )
        elif block.type == "tool_result":
            content.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "content": block.content,
                    "is_error": block.is_error,
                }
            )
        elif block.type == "thinking":
            content.append({"type": "thinking", "thinking": block.thinking})
        elif block.type == "redacted_thinking":
            content.append({"type": "redacted_thinking", "data": block.data})
        elif block.type == "image":
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": block.source.media_type,
                        "data": block.source.data,
                    },
                }
            )
    return {"role": message.role, "content": content}


def _tool_to_api(tool: Tool) -> dict[str, Any]:
    if callable(tool.description):
        description = tool.description(None)
    else:
        description = tool.description
    return {
        "name": tool.name,
        "description": description,
        "input_schema": tool.input_schema or {"type": "object", "properties": {}},
    }


def _extract_latest_user_text(messages: list[Message]) -> str:
    for message in reversed(messages):
        if message.role != "user":
            continue
        text_parts = [b.text for b in message.content if getattr(b, "type", None) == "text"]
        if text_parts:
            return "\n".join(text_parts)
    return ""


def _mock_tool_use(prompt: str) -> ToolUseBlock | None:
    match = re.search(r"\[\[tool:(?P<name>[A-Za-z0-9_\-]+)\s*(?P<input>\{.*\})?\]\]", prompt)
    if not match:
        return None
    name = match.group("name")
    raw_input = match.group("input") or "{}"
    try:
        input_obj = json.loads(raw_input)
    except json.JSONDecodeError:
        input_obj = {}
    return ToolUseBlock(type="tool_use", id="mock-tool-use-1", name=name, input=input_obj)


async def _mock_call(
    messages: list[Message],
    tools: list[Tool],
) -> AsyncGenerator[StreamEvent, None]:
    latest = _extract_latest_user_text(messages)
    tool_use = _mock_tool_use(latest)
    if tool_use and not any(t.name == tool_use.name for t in tools):
        tool_use = None

    base_text = "[mock] RTE-AI received your request."
    if tool_use:
        base_text += f" Requesting tool {tool_use.name}."
    for chunk in [base_text]:
        yield {"type": "assistant_text", "text": chunk}

    content = [TextBlock(type="text", text=base_text)]
    if tool_use:
        content.append(tool_use)
        yield {"type": "tool_use", "tool_use": tool_use}

    message = Message(role="assistant", content=content)
    usage = TokenUsage(
        input_tokens=max(1, len(latest) // 4), output_tokens=max(1, len(base_text) // 4)
    )
    set_last_usage(usage)
    yield {"type": "assistant_message", "message": message}
    yield {"type": "usage", "usage": usage}
    yield {"type": "turn_complete", "stop_reason": "tool_use" if tool_use else "end_turn"}


async def _anthropic_call(
    messages: list[Message],
    tools: list[Tool],
    model_config: ModelConfig,
    system_prompt_blocks: list[SystemPromptBlock],
    api_key: str,
    api_base_url: str | None,
    enable_thinking: bool,
    thinking_budget: int | None,
) -> AsyncGenerator[StreamEvent, None]:
    if Anthropic is None:
        async for event in _mock_call(messages, tools):
            yield event
        return

    system_text = "\n\n".join(block.text for block in system_prompt_blocks)
    api_messages = [_message_to_api(msg) for msg in messages]
    api_tools = [_tool_to_api(tool) for tool in tools]
    client = Anthropic(api_key=api_key, base_url=api_base_url or os.getenv("ANTHROPIC_BASE_URL"))

    request: dict[str, Any] = {
        "model": model_config.model,
        "max_tokens": model_config.max_output_tokens,
        "system": system_text,
        "messages": api_messages,
    }
    if api_tools:
        request["tools"] = api_tools

    if enable_thinking and model_config.supports_thinking:
        request["thinking"] = {
            "type": "enabled",
            "budget_tokens": thinking_budget or 10_000,
        }

    async def _invoke(_: int) -> Any:
        return await asyncio.to_thread(lambda: client.messages.create(**request))

    try:
        response = await with_retry(_invoke)
    except Exception as raw:
        error = classify_error(raw)
        if isinstance(error, PromptTooLongError):
            raise
        yield {"type": "error", "error": error}
        return

    content_blocks: list[Any] = []
    for block in response.content:
        if block.type == "text":
            text = block.text
            content_blocks.append(TextBlock(type="text", text=text))
            yield {"type": "assistant_text", "text": text}
        elif block.type == "tool_use":
            tool_use = ToolUseBlock(
                type="tool_use",
                id=block.id,
                name=block.name,
                input=block.input or {},
            )
            content_blocks.append(tool_use)
            yield {"type": "tool_use", "tool_use": tool_use}
        elif block.type == "thinking":
            thinking = ThinkingBlock(type="thinking", thinking=getattr(block, "thinking", ""))
            content_blocks.append(thinking)
            yield {"type": "thinking", "text": thinking.thinking}

    message = Message(role="assistant", content=content_blocks)
    usage = TokenUsage(
        input_tokens=(
            getattr(response.usage, "input_tokens", 0) if getattr(response, "usage", None) else 0
        ),
        output_tokens=(
            getattr(response.usage, "output_tokens", 0) if getattr(response, "usage", None) else 0
        ),
        cache_read_tokens=(
            getattr(response.usage, "cache_read_input_tokens", 0)
            if getattr(response, "usage", None)
            else 0
        ),
        cache_creation_tokens=(
            getattr(response.usage, "cache_creation_input_tokens", 0)
            if getattr(response, "usage", None)
            else 0
        ),
    )
    set_last_usage(usage)

    yield {"type": "assistant_message", "message": message}
    if usage.input_tokens or usage.output_tokens:
        yield {"type": "usage", "usage": usage}
    yield {
        "type": "turn_complete",
        "stop_reason": getattr(response, "stop_reason", "end_turn") or "end_turn",
    }


async def call_model(
    messages: list[Message],
    tools: list[Tool],
    model_config: ModelConfig,
    system_prompt_blocks: list[SystemPromptBlock],
    api_key: str,
    api_base_url: str | None = None,
    enable_thinking: bool = False,
    thinking_budget: int | None = None,
    abort_signal: Any | None = None,
) -> AsyncGenerator[StreamEvent, None]:
    del abort_signal
    if os.getenv("ENV_AGENT_MOCK", "").lower() in {"1", "true", "yes"} or not api_key:
        async for event in _mock_call(messages, tools):
            yield event
        return

    async for event in _anthropic_call(
        messages=messages,
        tools=tools,
        model_config=model_config,
        system_prompt_blocks=system_prompt_blocks,
        api_key=api_key,
        api_base_url=api_base_url,
        enable_thinking=enable_thinking,
        thinking_budget=thinking_budget,
    ):
        yield event
