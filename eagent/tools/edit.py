"""Edit tool for targeted find/replace edits."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from eagent.core.types import FileState, Tool, ToolContext, ToolResult
from eagent.files.atomic_write import atomic_write


def _count_occurrences(content: str, needle: str) -> int:
    if not needle:
        return 0
    return content.count(needle)


def _diff_preview(old: str, new: str, context: int = 3) -> str:
    diff = difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile="before",
        tofile="after",
        lineterm="",
        n=context,
    )
    text = "\n".join(diff)
    return text[:4000]


async def _call(input_data: dict[str, Any], context: ToolContext) -> ToolResult:
    raw_path = str(
        input_data.get("file_path") or input_data.get("path") or input_data.get("filePath") or ""
    )
    if not raw_path:
        return ToolResult(result="Error: file_path parameter is required.", is_error=True)

    old_string = str(input_data.get("old_string") or "")
    new_string = str(input_data.get("new_string") or "")
    replace_all = bool(input_data.get("replace_all") or False)

    file_path = Path(raw_path)
    if not file_path.is_absolute():
        file_path = Path(context.cwd) / file_path
    file_path = file_path.resolve()

    if old_string == new_string:
        return ToolResult(result="Error: old_string and new_string are identical.", is_error=True)

    exists = file_path.exists()

    if old_string == "" and not exists:
        atomic_write(str(file_path), new_string)
        context.modified_files.add(str(file_path))
        context.file_history.tracked_files.add(str(file_path))
        context.read_file_state.set(
            str(file_path),
            FileState(content=new_string, timestamp=file_path.stat().st_mtime * 1000),
        )
        return ToolResult(
            result=f"Created new file: {file_path} ({len(new_string.splitlines())} lines)"
        )

    if not exists:
        return ToolResult(
            result=(
                f"Error: file not found: {file_path}. To create a new file, set old_string to empty string."
            ),
            is_error=True,
        )

    cached_state = context.read_file_state.get(str(file_path))
    if cached_state is None:
        return ToolResult(
            result=f"Error: you must Read the file before editing it. Use Read on {file_path} first.",
            is_error=True,
        )

    if cached_state.is_partial_view and old_string not in cached_state.content:
        return ToolResult(
            result=(
                "Error: the file was only partially read and the target text was not in the cached segment. "
                "Read full file or relevant section first."
            ),
            is_error=True,
        )

    current_mtime = file_path.stat().st_mtime * 1000
    if current_mtime > cached_state.timestamp + 1000:
        return ToolResult(
            result="Error: file changed after last read. Read file again before editing.",
            is_error=True,
        )

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        return ToolResult(result=f"Error reading file: {exc}", is_error=True)

    if old_string not in content:
        trimmed = old_string.strip()
        if trimmed and trimmed in content:
            return ToolResult(
                result=(
                    "Error: exact match not found, but a whitespace-trimmed match exists. "
                    "Ensure old_string matches exact whitespace and line breaks."
                ),
                is_error=True,
            )
        return ToolResult(result=f"Error: old_string not found in {file_path}", is_error=True)

    occurrences = _count_occurrences(content, old_string)
    if occurrences > 1 and not replace_all:
        return ToolResult(
            result=(
                f"Error: old_string appears {occurrences} times. Provide more specific context or set replace_all=true."
            ),
            is_error=True,
        )

    new_content = (
        content.replace(old_string, new_string)
        if replace_all
        else content.replace(old_string, new_string, 1)
    )
    if new_content == content:
        return ToolResult(result="No changes applied.")

    try:
        atomic_write(str(file_path), new_content)
    except Exception as exc:
        return ToolResult(result=f"Error writing file: {exc}", is_error=True)

    context.modified_files.add(str(file_path))
    context.file_history.tracked_files.add(str(file_path))
    context.read_file_state.set(
        str(file_path),
        FileState(content=new_content, timestamp=file_path.stat().st_mtime * 1000),
    )

    preview = _diff_preview(content, new_content)
    return ToolResult(result=f"Edited: {file_path}\n\n{preview}")


def build_edit_tool() -> Tool:
    return Tool(
        name="Edit",
        description="Apply targeted text replacement in a file.",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
                "replace_all": {"type": "boolean"},
            },
            "required": ["file_path", "old_string", "new_string"],
            "additionalProperties": False,
        },
        call=_call,
        prompt=lambda: "Use Edit for small, precise changes. Read file first.",
        is_read_only=lambda _i: False,
        is_concurrency_safe=lambda _i: False,
        max_result_size_chars=30_000,
        user_facing_name=lambda input_data: f"Edit: {input_data.get('file_path') or input_data.get('path')}",
    )
