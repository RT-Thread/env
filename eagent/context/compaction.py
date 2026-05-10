"""Conversation compaction logic."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from eagent.context.token_counting import estimate_message_tokens
from eagent.core.types import Message, SystemPromptBlock, TextBlock
from eagent.prompt.compact_prompt import COMPACT_PROMPT, format_compact_summary

PRESERVE_RECENT_TURNS = 3
SAFETY_MARGIN = 13_000


@dataclass
class CompactParams:
    api_key: str
    model: str
    system_prompt_blocks: list[SystemPromptBlock] | None = None
    custom_prompt: str | None = None


@dataclass
class CompactResult:
    compacted: list[Message]
    old_tokens: int
    new_tokens: int


async def compact(
    messages: list[Message],
    params: CompactParams,
    call_model: Callable[[str, str, str, str], Awaitable[str]],
) -> CompactResult:
    old_tokens = estimate_message_tokens(messages)
    if len(messages) <= PRESERVE_RECENT_TURNS * 2:
        return CompactResult(compacted=messages, old_tokens=old_tokens, new_tokens=old_tokens)

    keep = messages[-(PRESERVE_RECENT_TURNS * 2) :]
    summarize = messages[: -(PRESERVE_RECENT_TURNS * 2)]

    serialized: list[str] = []
    for message in summarize:
        serialized.append(message.role.upper())
        for block in message.content:
            if getattr(block, "type", None) == "text":
                serialized.append(getattr(block, "text", ""))
            elif getattr(block, "type", None) == "tool_use":
                serialized.append(
                    f"[TOOL_USE] {getattr(block, 'name', '')} {getattr(block, 'input', {})}"
                )
            elif getattr(block, "type", None) == "tool_result":
                serialized.append(f"[TOOL_RESULT] {getattr(block, 'content', '')}")

    prompt = (params.custom_prompt or COMPACT_PROMPT).strip() + "\n\n" + "\n".join(serialized)
    system_prompt = "You are a summarizer. Preserve file paths, commands, and decisions."
    summary = await call_model(system_prompt, prompt, params.model, params.api_key)

    summary_msg = Message(
        role="user",
        content=[TextBlock(type="text", text=format_compact_summary(summary))],
    )
    compacted = [summary_msg, *keep]
    new_tokens = estimate_message_tokens(compacted)
    return CompactResult(compacted=compacted, old_tokens=old_tokens, new_tokens=new_tokens)


def should_auto_compact(
    messages: list[Message], context_window: int, max_output_tokens: int
) -> bool:
    threshold = context_window - max_output_tokens - SAFETY_MARGIN
    return threshold > 0 and estimate_message_tokens(messages) >= threshold
