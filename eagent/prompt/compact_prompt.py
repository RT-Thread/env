"""Conversation compaction prompts."""

from __future__ import annotations

COMPACT_BOUNDARY_MARKER = "[CONVERSATION_COMPACTED]"

COMPACT_SYSTEM_INSTRUCTION = (
    "You are a conversation summarizer. Only summarize the conversation in a structured way."
)

COMPACT_PROMPT = """Summarize the following conversation in detail.
Use sections:
1) Primary request and intent
2) Technical concepts
3) Files and code sections
4) Errors and fixes
5) Problem solving
6) All user messages
7) Pending tasks
8) Current work
9) Optional next step
Keep identifiers, paths, and commands concrete.
"""


def format_compact_summary(summary: str) -> str:
    return (
        f"{COMPACT_BOUNDARY_MARKER}\n\n"
        "The following is a summary of previous conversation. Continue from it.\n\n"
        f"{summary}\n"
    )


def serialize_messages_for_compact(messages: list[dict[str, object]]) -> str:
    lines: list[str] = []
    for msg in messages:
        role = str(msg.get("role", "unknown")).upper()
        lines.append(f"--- {role} ---")
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    btype = block.get("type")
                    if btype == "text":
                        lines.append(str(block.get("text", "")))
                    elif btype == "tool_use":
                        lines.append(f"[Tool call] {block.get('name')} {block.get('input')}")
                    elif btype == "tool_result":
                        lines.append(f"[Tool result] {block.get('content')}")
        lines.append("")
    return "\n".join(lines)
