"""Ask tool for requesting clarification from user."""

from __future__ import annotations

from typing import Any

from eagent.core.types import Tool, ToolContext, ToolResult


async def _call(input_data: dict[str, Any], context: ToolContext) -> ToolResult:
    _ = context
    question = str(input_data.get("question") or "").strip()
    if not question:
        return ToolResult(result="Error: question is required.", is_error=True)
    return ToolResult(result=f"[ASK_USER] {question}")


def build_ask_tool() -> Tool:
    return Tool(
        name="Ask",
        description="Request clarification from user.",
        input_schema={
            "type": "object",
            "properties": {
                "question": {"type": "string"},
            },
            "required": ["question"],
            "additionalProperties": False,
        },
        call=_call,
        prompt=lambda: "Use Ask when required input is missing and assumptions are risky.",
        is_read_only=lambda _i: True,
        is_concurrency_safe=lambda _i: False,
        max_result_size_chars=10_000,
        user_facing_name=lambda _i: "Ask",
    )
