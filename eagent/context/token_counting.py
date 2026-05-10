"""Fast token estimation utilities."""

from __future__ import annotations

from eagent.core.types import Message, SystemPromptBlock

CHARS_PER_TOKEN = 4
JSON_CHARS_PER_TOKEN = 2


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return round(len(text) / CHARS_PER_TOKEN)


def estimate_json_tokens(obj: object) -> int:
    import json

    try:
        return round(len(json.dumps(obj, ensure_ascii=False)) / JSON_CHARS_PER_TOKEN)
    except Exception:
        return 0


def estimate_single_message_tokens(message: Message) -> int:
    total = 4
    for block in message.content:
        btype = getattr(block, "type", None)
        if btype == "text":
            total += estimate_tokens(getattr(block, "text", ""))
        elif btype == "tool_use":
            total += estimate_tokens(getattr(block, "name", ""))
            total += estimate_json_tokens(getattr(block, "input", {}))
        elif btype == "tool_result":
            content = getattr(block, "content", "")
            if isinstance(content, str):
                total += estimate_tokens(content)
            else:
                total += estimate_json_tokens(content)
        elif btype == "thinking":
            total += estimate_tokens(getattr(block, "thinking", ""))
        elif btype == "redacted_thinking":
            total += estimate_tokens(getattr(block, "data", ""))
        elif btype == "image":
            total += 1500
    return total


def estimate_message_tokens(messages: list[Message]) -> int:
    return sum(estimate_single_message_tokens(m) for m in messages)


def estimate_system_prompt_tokens(blocks: list[SystemPromptBlock]) -> int:
    return sum(estimate_tokens(b.text) for b in blocks)


def truncate_to_token_budget(text: str, max_tokens: int) -> str:
    if estimate_tokens(text) <= max_tokens:
        return text
    limit = max_tokens * CHARS_PER_TOKEN
    clipped = text[:limit]
    idx = max(clipped.rfind("\n"), clipped.rfind(" "))
    if idx > 0:
        return f"{clipped[:idx]}\n...[truncated]"
    return f"{clipped}...[truncated]"
