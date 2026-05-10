"""Streaming event helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from eagent.core.types import StreamEvent


async def collect_assistant_text(events: AsyncGenerator[StreamEvent, None]) -> str:
    chunks: list[str] = []
    async for event in events:
        if event["type"] == "assistant_text":
            chunks.append(event["text"])
    return "".join(chunks)


def event_to_log_line(event: StreamEvent) -> str:
    event_type = event.get("type", "unknown")
    if event_type == "assistant_text":
        return event.get("text", "")
    if event_type == "tool_start":
        return f"[tool:start] {event.get('tool_name')}"
    if event_type == "tool_result":
        status = "error" if event.get("is_error") else "ok"
        return f"[tool:{status}] {event.get('tool_name')}: {event.get('result', '')[:120]}"
    if event_type == "compact":
        return f"[compact] {event.get('old_tokens')} -> {event.get('new_tokens')}"
    if event_type == "usage":
        usage = event.get("usage")
        if usage:
            return (
                f"[usage] in={usage.input_tokens} out={usage.output_tokens} "
                f"cache_r={usage.cache_read_tokens} cache_w={usage.cache_creation_tokens}"
            )
    if event_type == "error":
        return f"[error] {event.get('error')}"
    if event_type == "hook_debug":
        return f"[hook] {event.get('text', '')}"
    return f"[{event_type}]"
