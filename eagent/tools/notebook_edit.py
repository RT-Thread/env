"""NotebookEdit tool for minimal Jupyter cell updates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eagent.core.types import Tool, ToolContext, ToolResult
from eagent.files.atomic_write import atomic_write


async def _call(input_data: dict[str, Any], context: ToolContext) -> ToolResult:
    raw_path = str(input_data.get("file_path") or "")
    cell_index = int(input_data.get("cell_index") or -1)
    new_source = input_data.get("new_source")

    if not raw_path:
        return ToolResult(result="Error: file_path is required.", is_error=True)
    if cell_index < 0:
        return ToolResult(result="Error: cell_index must be >= 0.", is_error=True)
    if new_source is None:
        return ToolResult(result="Error: new_source is required.", is_error=True)

    path = Path(raw_path)
    if not path.is_absolute():
        path = Path(context.cwd) / path
    path = path.resolve()

    try:
        notebook = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ToolResult(result=f"Error reading notebook: {exc}", is_error=True)

    cells = notebook.get("cells")
    if not isinstance(cells, list):
        return ToolResult(result="Error: invalid notebook format (missing cells).", is_error=True)
    if cell_index >= len(cells):
        return ToolResult(
            result=f"Error: cell_index out of range (0..{len(cells)-1}).", is_error=True
        )

    source_text = str(new_source)
    cells[cell_index]["source"] = source_text.splitlines(keepends=True)

    try:
        atomic_write(str(path), json.dumps(notebook, ensure_ascii=False, indent=2) + "\n")
    except Exception as exc:
        return ToolResult(result=f"Error writing notebook: {exc}", is_error=True)

    context.modified_files.add(str(path))
    context.file_history.tracked_files.add(str(path))

    return ToolResult(result=f"Updated notebook cell {cell_index} in {path}.")


def build_notebook_edit_tool() -> Tool:
    return Tool(
        name="NotebookEdit",
        description="Edit a Jupyter notebook cell by index.",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "cell_index": {"type": "integer", "minimum": 0},
                "new_source": {"type": "string"},
            },
            "required": ["file_path", "cell_index", "new_source"],
            "additionalProperties": False,
        },
        call=_call,
        prompt=lambda: "Use NotebookEdit for focused notebook cell changes.",
        is_read_only=lambda _i: False,
        is_concurrency_safe=lambda _i: False,
        max_result_size_chars=10_000,
        user_facing_name=lambda input_data: f"NotebookEdit: {input_data.get('file_path')}",
    )
