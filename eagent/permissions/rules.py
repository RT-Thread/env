"""Permission rule loading and matching."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from eagent.core.types import PermissionRule
from eagent.paths import env_root

PROJECT_CONFIG_DIR = ".agents"


def _read_settings(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _extract_rules(settings: dict[str, Any] | None, source: str) -> list[PermissionRule]:
    if not settings:
        return []
    permissions = settings.get("permissions")
    if not isinstance(permissions, dict):
        return []

    out: list[PermissionRule] = []
    for behavior in ("allow", "deny"):
        entries = permissions.get(behavior)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            tool = entry.get("tool")
            if not isinstance(tool, str):
                continue
            content = entry.get("content")
            out.append(
                PermissionRule(
                    tool=tool,
                    behavior=behavior,  # type: ignore[arg-type]
                    source=source,  # type: ignore[arg-type]
                    content=content if isinstance(content, str) else None,
                )
            )
    return out


async def load_project_rules(cwd: str) -> list[PermissionRule]:
    root = Path(cwd).resolve()
    rules: list[PermissionRule] = []
    rules.extend(_extract_rules(_read_settings(root / PROJECT_CONFIG_DIR / "settings.json"), "project"))
    return rules


async def load_user_rules() -> list[PermissionRule]:
    rules: list[PermissionRule] = []
    rules.extend(_extract_rules(_read_settings(env_root() / "settings.json"), "user"))
    return rules


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    esc = ""
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*" and i + 1 < len(pattern) and pattern[i + 1] == "*":
            esc += ".*"
            i += 2
        elif ch == "*":
            esc += "[^/]*"
            i += 1
        elif ch == "?":
            esc += "[^/]"
            i += 1
        else:
            esc += re.escape(ch)
            i += 1
    return re.compile(f"^{esc}$")


def _glob_match(pattern: str, value: str) -> bool:
    try:
        return bool(_glob_to_regex(pattern).match(value))
    except re.error:
        return False


def _match_tool(tool_name: str, rule_pattern: str) -> bool:
    if tool_name == rule_pattern:
        return True
    if rule_pattern.startswith("mcp__") and rule_pattern.endswith("__"):
        return tool_name.startswith(rule_pattern)
    if "*" in rule_pattern or "?" in rule_pattern:
        return _glob_match(rule_pattern, tool_name)
    return False


def _match_content(tool_name: str, input_data: dict[str, Any], pattern: str) -> bool:
    name = tool_name.lower()
    if name == "bash":
        command = input_data.get("command") or input_data.get("cmd") or ""
        return isinstance(command, str) and _glob_match(pattern, command)

    file_path = (
        input_data.get("file_path")
        or input_data.get("path")
        or input_data.get("filePath")
        or input_data.get("filename")
    )
    if isinstance(file_path, str) and file_path:
        return _glob_match(pattern, file_path)

    for value in input_data.values():
        if isinstance(value, str) and _glob_match(pattern, value):
            return True
    return False


def match_rule(tool_name: str, input_data: dict[str, Any], rule: PermissionRule) -> bool:
    if not _match_tool(tool_name, rule.tool):
        return False
    if not rule.content:
        return True
    return _match_content(tool_name, input_data, rule.content)
