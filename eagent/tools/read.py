"""Read tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from eagent.core.types import FileState, Tool, ToolContext, ToolResult
from eagent.files.utils import detect_encoding, format_with_line_numbers, is_binary_data

DEFAULT_LIMIT = 2000
MAX_RESULT_SIZE_CHARS = 60_000
IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".webp",
    ".tiff",
    ".tif",
    ".psd",
    ".raw",
    ".heif",
    ".heic",
}


async def _call(input_data: dict[str, Any], context: ToolContext) -> ToolResult:
    raw_path = str(input_data.get("file_path") or input_data.get("path") or "")
    if not raw_path:
        return ToolResult(result="Error: file_path parameter is required.", is_error=True)

    file_path = Path(raw_path)
    if not file_path.is_absolute():
        file_path = Path(context.cwd) / file_path
    file_path = file_path.resolve()

    offset = int(input_data.get("offset") or 1)
    limit = int(input_data.get("limit") or DEFAULT_LIMIT)
    offset = max(1, offset)
    limit = max(1, limit)

    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        return ToolResult(
            result=f"This is an image file ({file_path.suffix}). Use an image-capable viewer.",
            is_error=False,
        )

    try:
        data = file_path.read_bytes()
    except FileNotFoundError:
        return ToolResult(result=f"Error: file not found: {file_path}", is_error=True)
    except IsADirectoryError:
        return ToolResult(
            result=f"Error: {file_path} is a directory. Use Glob or Bash ls/find to inspect it.",
            is_error=True,
        )
    except PermissionError:
        return ToolResult(result=f"Error: permission denied: {file_path}", is_error=True)
    except Exception as exc:
        return ToolResult(result=f"Error reading file: {exc}", is_error=True)

    if is_binary_data(data):
        return ToolResult(result=f"This is a binary file ({len(data)} bytes).", is_error=False)

    encoding = detect_encoding(data)
    if encoding == "utf-16le":
        content = data[2:].decode("utf-16le", errors="replace")
    else:
        content = data.decode("utf-8-sig", errors="replace")

    all_lines = content.split("\n")
    total = len(all_lines)
    start = offset - 1
    end = min(start + limit, total)
    selected = all_lines[start:end]

    rendered = format_with_line_numbers("\n".join(selected), start_line=offset)
    if start > 0 or end < total:
        meta: list[str] = []
        if start > 0:
            meta.append(f"(showing from line {offset})")
        if end < total:
            meta.append(f"({total - end} more lines below, {total} total)")
        rendered += "\n" + " ".join(meta)

    context.read_file_state.set(
        str(file_path),
        FileState(
            content=content,
            timestamp=file_path.stat().st_mtime * 1000,
            offset=offset,
            limit=limit,
            is_partial_view=start > 0 or end < total,
        ),
    )

    if len(rendered) > MAX_RESULT_SIZE_CHARS:
        rendered = (
            rendered[:MAX_RESULT_SIZE_CHARS]
            + f"\n\n[Output truncated at {MAX_RESULT_SIZE_CHARS} chars]"
        )

    return ToolResult(result=rendered)


def build_read_tool() -> Tool:
    return Tool(
        name="Read",
        description="Read a file with line numbers.",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "offset": {"type": "integer", "minimum": 1},
                "limit": {"type": "integer", "minimum": 1},
            },
            "required": ["file_path"],
            "additionalProperties": False,
        },
        call=_call,
        prompt=lambda: "Read files before editing; use offset/limit for large files.",
        is_read_only=lambda _i: True,
        is_concurrency_safe=lambda _i: True,
        max_result_size_chars=MAX_RESULT_SIZE_CHARS,
        user_facing_name=lambda input_data: f"Read: {input_data.get('file_path') or input_data.get('path')}",
    )
