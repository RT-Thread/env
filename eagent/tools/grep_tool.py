"""Grep-like regex search tool."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from eagent.core.types import Tool, ToolContext, ToolResult

MAX_MATCH_LINES = 2000


async def _call(input_data: dict[str, Any], context: ToolContext) -> ToolResult:
    pattern = str(input_data.get("pattern") or "")
    if not pattern:
        return ToolResult(result="Error: pattern parameter is required.", is_error=True)

    base = str(input_data.get("path") or context.cwd)
    include = str(input_data.get("include") or "")
    case_sensitive = bool(input_data.get("case_sensitive") or False)

    root = Path(base)
    if not root.is_absolute():
        root = Path(context.cwd) / root
    root = root.resolve()

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        regex = re.compile(pattern, flags)
    except re.error as exc:
        return ToolResult(result=f"Error: invalid regex: {exc}", is_error=True)

    files: list[Path] = []
    if include:
        files = [p for p in root.rglob(include) if p.is_file()]
    else:
        files = [p for p in root.rglob("*") if p.is_file()]

    matches: list[str] = []
    for file_path in files:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                path_display = (
                    str(file_path.relative_to(context.cwd))
                    if str(file_path).startswith(context.cwd)
                    else str(file_path)
                )
                matches.append(f"{path_display}:{idx}:{line}")
                if len(matches) >= MAX_MATCH_LINES:
                    matches.append(f"... truncated at {MAX_MATCH_LINES} matches")
                    return ToolResult(result="\n".join(matches))

    if not matches:
        return ToolResult(result="No matches found.")
    return ToolResult(result="\n".join(matches))


def build_grep_tool() -> Tool:
    return Tool(
        name="Grep",
        description="Search text by regex across files.",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string"},
                "include": {"type": "string"},
                "case_sensitive": {"type": "boolean"},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
        call=_call,
        prompt=lambda: "Use Grep for content search with regex patterns.",
        is_read_only=lambda _i: True,
        is_concurrency_safe=lambda _i: True,
        max_result_size_chars=100_000,
        user_facing_name=lambda input_data: f"Grep: {input_data.get('pattern')}",
    )
