"""Write tool for complete file overwrite/create."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from eagent.core.types import FileState, Tool, ToolContext, ToolResult
from eagent.files.atomic_write import atomic_write


async def _call(input_data: dict[str, Any], context: ToolContext) -> ToolResult:
    raw_path = str(
        input_data.get("file_path") or input_data.get("path") or input_data.get("filePath") or ""
    )
    if not raw_path:
        return ToolResult(result="Error: file_path parameter is required.", is_error=True)

    content = str(input_data.get("content") or "")

    file_path = Path(raw_path)
    if not file_path.is_absolute():
        file_path = Path(context.cwd) / file_path
    file_path = file_path.resolve()

    if file_path.exists():
        cached = context.read_file_state.get(str(file_path))
        if cached is None:
            return ToolResult(
                result=(
                    f"Error: file already exists at {file_path}. Read it first before overwrite, "
                    "or use Edit for targeted updates."
                ),
                is_error=True,
            )
        current_mtime = file_path.stat().st_mtime * 1000
        if current_mtime > cached.timestamp + 1000:
            return ToolResult(
                result="Error: file changed after last read. Read again before write.",
                is_error=True,
            )

    try:
        atomic_write(str(file_path), content)
    except PermissionError:
        return ToolResult(result=f"Error: permission denied writing to {file_path}", is_error=True)
    except Exception as exc:
        return ToolResult(result=f"Error writing file: {exc}", is_error=True)

    context.modified_files.add(str(file_path))
    context.file_history.tracked_files.add(str(file_path))
    context.read_file_state.set(
        str(file_path),
        FileState(content=content, timestamp=file_path.stat().st_mtime * 1000),
    )

    return ToolResult(result=f"Written: {file_path} ({len(content.splitlines())} lines)")


def build_write_tool() -> Tool:
    return Tool(
        name="Write",
        description="Write complete file content (create or overwrite).",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["file_path", "content"],
            "additionalProperties": False,
        },
        call=_call,
        prompt=lambda: "Use Write for full-file creation/overwrite. Prefer Edit for targeted changes.",
        is_read_only=lambda _i: False,
        is_concurrency_safe=lambda _i: False,
        max_result_size_chars=30_000,
        user_facing_name=lambda input_data: f"Write: {input_data.get('file_path') or input_data.get('path')}",
    )
