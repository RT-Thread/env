"""Agent delegation tool."""

from __future__ import annotations

from typing import Any

from eagent.core.types import QueryParams, Tool, ToolContext, ToolResult

_AGENT_PARAMS: QueryParams | None = None


def set_agent_query_params(params: QueryParams | None) -> None:
    global _AGENT_PARAMS
    _AGENT_PARAMS = params


async def _call(input_data: dict[str, Any], context: ToolContext) -> ToolResult:
    prompt = str(input_data.get("prompt") or "").strip()
    if not prompt:
        return ToolResult(result="Error: prompt is required.", is_error=True)
    if _AGENT_PARAMS is None:
        return ToolResult(result="Error: agent context not initialized.", is_error=True)

    tools = input_data.get("tools")
    disallowed_tools = input_data.get("disallowed_tools")
    max_turns = input_data.get("max_turns")
    model = input_data.get("model")

    from eagent.core.agent_loop import run_sub_agent

    try:
        text = await run_sub_agent(
            prompt,
            _AGENT_PARAMS,
            tools=tools if isinstance(tools, list) else None,
            disallowed_tools=disallowed_tools if isinstance(disallowed_tools, list) else None,
            max_turns=int(max_turns) if isinstance(max_turns, int) else None,
            model=str(model) if isinstance(model, str) else None,
        )
        return ToolResult(result=text)
    except Exception as exc:
        return ToolResult(result=f"Sub-agent failed: {exc}", is_error=True)


def build_agent_tool() -> Tool:
    return Tool(
        name="Agent",
        description="Run a delegated sub-task in an isolated sub-agent.",
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "tools": {"type": "array", "items": {"type": "string"}},
                "disallowed_tools": {"type": "array", "items": {"type": "string"}},
                "max_turns": {"type": "integer", "minimum": 1},
                "model": {"type": "string"},
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
        call=_call,
        prompt=lambda: "Delegate bounded sub-tasks when parallel or isolated reasoning is beneficial.",
        is_read_only=lambda _i: False,
        is_concurrency_safe=lambda _i: False,
        max_result_size_chars=100_000,
        user_facing_name=lambda _i: "Agent",
    )
