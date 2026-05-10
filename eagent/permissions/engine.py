"""Central permission decision engine."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eagent.core.types import PermissionDecision, PermissionRule
from eagent.permissions.modes import get_mode_restrictions
from eagent.permissions.rules import load_project_rules, load_user_rules, match_rule

_session_rules: list[PermissionRule] = []

READ_ONLY_PREFIXES = (
    "ls",
    "cat",
    "head",
    "tail",
    "wc",
    "grep",
    "rg",
    "find",
    "fd",
    "pwd",
    "echo",
    "date",
    "git log",
    "git status",
    "git diff",
    "git show",
)


def add_session_rule(rule: PermissionRule) -> None:
    _session_rules.append(rule)


def get_session_rules() -> list[PermissionRule]:
    return list(_session_rules)


def clear_session_rules() -> None:
    _session_rules.clear()


def is_read_only_command(command: str) -> bool:
    cmd = command.strip()
    return any(
        cmd == prefix or cmd.startswith(prefix + " ") or cmd.startswith(prefix + "\t")
        for prefix in READ_ONLY_PREFIXES
    )


@dataclass(frozen=True)
class PermissionContext:
    cwd: str
    permission_mode: str
    tools: list[Any]


def _resolve_path(raw_path: str, cwd: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path(cwd) / path
    return path.resolve(strict=False)


def _is_within(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _collect_candidate_paths(input_data: dict[str, Any], cwd: str) -> list[Path]:
    path_keys = ("file_path", "path", "filePath", "filename", "directory")
    list_keys = ("paths", "files")
    paths: list[Path] = []

    for key in path_keys:
        value = input_data.get(key)
        if isinstance(value, str) and value.strip():
            paths.append(_resolve_path(value, cwd))

    for key in list_keys:
        value = input_data.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, str) and item.strip():
                paths.append(_resolve_path(item, cwd))

    return paths


def _collect_bash_command_paths(input_data: dict[str, Any], cwd: str) -> list[Path]:
    command = input_data.get("command") or input_data.get("cmd")
    if not isinstance(command, str) or not command.strip():
        return []

    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return []

    candidates: list[Path] = []
    for token in tokens:
        trimmed = token.strip()
        if not trimmed:
            continue
        cleaned = trimmed.lstrip("><").rstrip(",;")
        if not cleaned:
            continue
        if cleaned.startswith("-"):
            continue
        if cleaned.startswith(("http://", "https://")):
            continue
        if cleaned.startswith(("/", "~/", "./", "../")) or "/" in cleaned:
            candidates.append(_resolve_path(cleaned, cwd))

    return candidates


async def check_permission(
    tool_name: str, input_data: dict[str, Any], context: PermissionContext
) -> PermissionDecision:
    project_rules = await load_project_rules(context.cwd)
    user_rules = await load_user_rules()
    all_rules = [*_session_rules, *project_rules, *user_rules]

    for rule in all_rules:
        if rule.behavior == "deny" and match_rule(tool_name, input_data, rule):
            return PermissionDecision(
                behavior="deny", message=f"Denied by {rule.source} rule: {rule.tool}"
            )

    if context.permission_mode == "bypassPermissions":
        return PermissionDecision(behavior="allow")

    for rule in all_rules:
        if rule.behavior == "allow" and match_rule(tool_name, input_data, rule):
            return PermissionDecision(behavior="allow")

    tool_def = next((t for t in context.tools if getattr(t, "name", None) == tool_name), None)
    restrictions = get_mode_restrictions(context.permission_mode)  # type: ignore[arg-type]
    is_read_only_tool = False
    if tool_def is not None:
        try:
            is_read_only_tool = bool(tool_def.is_read_only(input_data))
        except Exception:
            is_read_only_tool = False

    if context.permission_mode == "plan":
        if restrictions.allow_writes or is_read_only_tool:
            return PermissionDecision(behavior="allow")
        return PermissionDecision(
            behavior="deny", message="Write operations are not allowed in plan mode."
        )

    cwd_root = Path(context.cwd).expanduser().resolve(strict=False)
    candidate_paths = _collect_candidate_paths(input_data, context.cwd)
    if tool_name.lower() == "bash":
        candidate_paths.extend(_collect_bash_command_paths(input_data, context.cwd))

    if candidate_paths:
        outside_paths = [path for path in candidate_paths if not _is_within(cwd_root, path)]
        if not outside_paths:
            return PermissionDecision(behavior="allow")
        outside_path = str(outside_paths[0])
        return PermissionDecision(
            behavior="ask",
            message=(
                f'Path "{outside_path}" is outside current directory "{cwd_root}". '
                "Please choose Allow or Deny for this request."
            ),
        )

    if tool_name.lower() == "bash":
        return PermissionDecision(behavior="allow")

    if (
        context.permission_mode == "acceptEdits"
        and restrictions.allow_writes
        and tool_name in {"Edit", "Write", "NotebookEdit"}
    ):
        return PermissionDecision(behavior="allow")

    if is_read_only_tool:
        return PermissionDecision(behavior="allow")

    return PermissionDecision(behavior="ask", message=f'Tool "{tool_name}" requires permission.')
