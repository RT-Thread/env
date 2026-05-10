"""Glob tool for file discovery."""

from __future__ import annotations

import glob
from pathlib import Path
from typing import Any

from eagent.core.types import Tool, ToolContext, ToolResult

MAX_RESULTS = 1000


async def _call(input_data: dict[str, Any], context: ToolContext) -> ToolResult:
    pattern = str(input_data.get("pattern") or "")
    if not pattern:
        return ToolResult(result="Error: pattern parameter is required.", is_error=True)

    base = str(input_data.get("path") or context.cwd)
    base_path = Path(base)
    if not base_path.is_absolute():
        base_path = Path(context.cwd) / base_path
    base_path = base_path.resolve()

    full_pattern = str(base_path / pattern)
    matches = sorted(glob.glob(full_pattern, recursive=True))
    matches = [str(Path(m).resolve()) for m in matches][:MAX_RESULTS]

    if not matches:
        return ToolResult(result="No files matched.")

    rel = [
        str(Path(m).relative_to(context.cwd)) if str(Path(m)).startswith(context.cwd) else m
        for m in matches
    ]
    return ToolResult(result="\n".join(rel))


def build_glob_tool() -> Tool:
    return Tool(
        name="Glob",
        description="Find files by glob pattern.",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
        call=_call,
        prompt=lambda: "Use Glob to discover files before reading/editing.",
        is_read_only=lambda _i: True,
        is_concurrency_safe=lambda _i: True,
        max_result_size_chars=60_000,
        user_facing_name=lambda input_data: f"Glob: {input_data.get('pattern')}",
    )
