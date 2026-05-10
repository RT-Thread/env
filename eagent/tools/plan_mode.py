"""Plan mode helper tools."""

from __future__ import annotations

from typing import Any

from eagent.core.types import Tool, ToolContext, ToolResult


async def _enter_call(input_data: dict[str, Any], context: ToolContext) -> ToolResult:
    del input_data
    context.permission_mode = "plan"
    return ToolResult(result="Plan mode enabled (read-only).")


async def _exit_call(input_data: dict[str, Any], context: ToolContext) -> ToolResult:
    del input_data
    if context.permission_mode == "plan":
        context.permission_mode = "default"
    return ToolResult(result=f"Permission mode: {context.permission_mode}")


def build_enter_plan_mode_tool() -> Tool:
    return Tool(
        name="EnterPlanMode",
        description="Switch to read-only plan mode.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        call=_enter_call,
        prompt=lambda: "Switch to plan mode when only planning is required.",
        is_read_only=lambda _i: False,
        is_concurrency_safe=lambda _i: False,
        max_result_size_chars=2000,
        user_facing_name=lambda _i: "EnterPlanMode",
    )


def build_exit_plan_mode_tool() -> Tool:
    return Tool(
        name="ExitPlanMode",
        description="Return from plan mode to default mode.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        call=_exit_call,
        prompt=lambda: "Exit plan mode once implementation can start.",
        is_read_only=lambda _i: False,
        is_concurrency_safe=lambda _i: False,
        max_result_size_chars=2000,
        user_facing_name=lambda _i: "ExitPlanMode",
    )
