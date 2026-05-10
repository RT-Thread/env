"""Web fetch tool."""

from __future__ import annotations

from typing import Any

import httpx

from eagent.core.types import Tool, ToolContext, ToolResult

MAX_CHARS = 40_000


async def _call(input_data: dict[str, Any], context: ToolContext) -> ToolResult:
    _ = context
    url = str(input_data.get("url") or "").strip()
    if not url:
        return ToolResult(result="Error: url is required.", is_error=True)
    timeout = float(input_data.get("timeout") or 20)
    max_chars = int(input_data.get("max_chars") or MAX_CHARS)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url)
    except Exception as exc:
        return ToolResult(result=f"Error fetching URL: {exc}", is_error=True)

    content_type = response.headers.get("content-type", "")
    text = response.text
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[Truncated to {max_chars} chars]"

    return ToolResult(
        result=(
            f"URL: {response.url}\n"
            f"Status: {response.status_code}\n"
            f"Content-Type: {content_type}\n\n"
            f"{text}"
        ),
        is_error=response.status_code >= 400,
    )


def build_web_fetch_tool() -> Tool:
    return Tool(
        name="WebFetch",
        description="Fetch and return text from a URL.",
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "timeout": {"type": "number"},
                "max_chars": {"type": "integer", "minimum": 1000},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        call=_call,
        prompt=lambda: "Fetch a specific URL when precise page content is needed.",
        is_read_only=lambda _i: True,
        is_concurrency_safe=lambda _i: True,
        max_result_size_chars=80_000,
        user_facing_name=lambda input_data: f"WebFetch: {input_data.get('url')}",
    )
