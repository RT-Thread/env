"""Todo tool for lightweight task tracking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eagent.core.types import Tool, ToolContext, ToolResult
from eagent.paths import env_root


def _todo_file(session_id: str) -> Path:
    path = env_root() / "todo"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{session_id}.json"


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _save(path: Path, items: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def _call(input_data: dict[str, Any], context: ToolContext) -> ToolResult:
    action = str(input_data.get("action") or "list")
    text = str(input_data.get("text") or "").strip()
    idx = input_data.get("index")

    path = _todo_file(context.session_id)
    items = _load(path)

    if action == "add":
        if not text:
            return ToolResult(result="Error: text is required for add action.", is_error=True)
        items.append({"text": text, "done": False})
        _save(path, items)
        return ToolResult(result=f"Added todo #{len(items)}: {text}")

    if action == "done":
        if not isinstance(idx, int) or idx < 1 or idx > len(items):
            return ToolResult(
                result="Error: valid index is required for done action.", is_error=True
            )
        items[idx - 1]["done"] = True
        _save(path, items)
        return ToolResult(result=f"Marked todo #{idx} done.")

    if action == "remove":
        if not isinstance(idx, int) or idx < 1 or idx > len(items):
            return ToolResult(
                result="Error: valid index is required for remove action.", is_error=True
            )
        removed = items.pop(idx - 1)
        _save(path, items)
        return ToolResult(result=f"Removed todo #{idx}: {removed.get('text', '')}")

    lines = []
    for i, item in enumerate(items, start=1):
        mark = "x" if item.get("done") else " "
        lines.append(f"{i}. [{mark}] {item.get('text', '')}")
    return ToolResult(result="\n".join(lines) if lines else "No todos.")


def build_todo_tool() -> Tool:
    return Tool(
        name="Todo",
        description="Manage a simple per-session todo list.",
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "add", "done", "remove"]},
                "text": {"type": "string"},
                "index": {"type": "integer", "minimum": 1},
            },
            "additionalProperties": False,
        },
        call=_call,
        prompt=lambda: "Track progress with add/done/remove/list todo actions.",
        is_read_only=lambda _i: False,
        is_concurrency_safe=lambda _i: False,
        max_result_size_chars=20_000,
        user_facing_name=lambda _i: "Todo",
    )
