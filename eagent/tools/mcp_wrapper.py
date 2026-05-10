"""Helper for wrapping MCP tools as eagent tools."""

from __future__ import annotations

from typing import Any

from eagent.core.types import Tool, ToolContext, ToolResult


class McpToolClientProtocol:
    async def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]: ...


def wrap_mcp_tool(
    server_name: str, tool_name: str, description: str, input_schema: dict[str, Any], client: Any
) -> Tool:
    async def _call(input_data: dict[str, Any], _context: ToolContext) -> ToolResult:
        try:
            result = await client.call_tool(tool_name, input_data)
        except Exception as exc:
            return ToolResult(result=f"MCP tool error: {exc}", is_error=True)

        content = result.get("content", "") if isinstance(result, dict) else ""
        if isinstance(content, list):
            text_parts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(str(block.get("text", "")))
                    else:
                        text_parts.append(str(block))
                else:
                    text_parts.append(str(block))
            text = "\n".join(text_parts)
        else:
            text = str(content)

        is_error = (
            bool(result.get("isError") or result.get("is_error"))
            if isinstance(result, dict)
            else False
        )
        return ToolResult(result=text or "(empty result)", is_error=is_error)

    return Tool(
        name=f"mcp__{server_name}__{tool_name}",
        description=description or f"MCP tool: {tool_name}",
        input_schema=input_schema or {"type": "object"},
        call=_call,
        prompt=lambda: description or f"MCP tool from {server_name}",
        is_concurrency_safe=lambda _i: True,
        is_read_only=lambda _i: False,
        max_result_size_chars=200_000,
        user_facing_name=lambda _i: f"{server_name}:{tool_name}",
    )
