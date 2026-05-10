"""Hook loading and execution runtime."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from eagent.paths import env_root
from eagent.skills.loader import parse_frontmatter

HookEventName = Literal[
    "session_start",
    "session_end",
    "user_prompt_submit",
    "pre_tool_use",
    "post_tool_use",
    "stop",
    "before_command",
    "after_command",
    "on_error",
]
HookAction = Literal["bash", "prompt_append"]
HookFailureMode = Literal["continue", "abort"]

HOOK_EVENTS: tuple[HookEventName, ...] = (
    "session_start",
    "session_end",
    "user_prompt_submit",
    "pre_tool_use",
    "post_tool_use",
    "stop",
    "before_command",
    "after_command",
    "on_error",
)
HOOK_EVENT_DIR_ALIASES: dict[HookEventName, tuple[str, ...]] = {
    "session_start": ("session_start",),
    "session_end": ("session_end",),
    "user_prompt_submit": ("user_prompt_submit",),
    "pre_tool_use": ("pre_tool_use", "before_tool"),
    "post_tool_use": ("post_tool_use", "after_tool"),
    "stop": ("stop",),
    "before_command": ("before_command",),
    "after_command": ("after_command",),
    "on_error": ("on_error",),
}
PROJECT_HOOKS_DIR = Path(".agents") / "hooks"
USER_HOOKS_DIR = Path("hooks")
HOOKS_JSON_FILE_NAME = "hooks.json"
HOOKS_RUNTIME_DIR = Path(".agents") / "runtime"
DEFAULT_TIMEOUT_SECONDS = 120
_VALID_ACTIONS = {"bash", "prompt_append"}
_VALID_FAILURE_MODES = {"continue", "abort"}
_BRACE_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")
_DOLLAR_PATTERN = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_]*)")
_DOLLAR_BRACE_PATTERN = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
_EXPORT_PATTERN = re.compile(r"^\s*export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

_CLAUDE_EVENT_BY_INTERNAL: dict[HookEventName, str] = {
    "session_start": "SessionStart",
    "session_end": "SessionEnd",
    "user_prompt_submit": "UserPromptSubmit",
    "pre_tool_use": "PreToolUse",
    "post_tool_use": "PostToolUse",
    "stop": "Stop",
    "before_command": "BeforeCommand",
    "after_command": "AfterCommand",
    "on_error": "OnError",
}

_EVENT_TOKEN_TO_INTERNAL: dict[str, HookEventName] = {
    "sessionstart": "session_start",
    "sessionend": "session_end",
    "userpromptsubmit": "user_prompt_submit",
    "pretooluse": "pre_tool_use",
    "posttooluse": "post_tool_use",
    "stop": "stop",
    "beforecommand": "before_command",
    "aftercommand": "after_command",
    "onerror": "on_error",
}


@dataclass(frozen=True)
class HookDefinition:
    """Single hook entry loaded from markdown or hooks.json."""

    event: HookEventName
    name: str
    description: str
    match: str
    action: HookAction
    on_failure: HookFailureMode
    timeout_seconds: int
    command: str | None
    template: str
    source_path: Path
    source: Literal["markdown", "json"] = "markdown"
    pass_stdin_json: bool = False
    parse_stdout_decision: bool = False


@dataclass(frozen=True)
class HookCommandResult:
    """Result of bash hook execution."""

    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


@dataclass
class HookExecutionOutcome:
    """Aggregated hook execution output."""

    aborted: bool = False
    abort_reason: str | None = None
    prompt_appends: list[str] = field(default_factory=list)
    debug_lines: list[str] = field(default_factory=list)


def _to_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return str(value)


def _read_file(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    stripped = text.strip()
    return stripped if stripped else None


def _extract_title(text: str) -> str:
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            return line.lstrip("#").strip()[:100]
        return line[:100]
    return "Hook"


def _normalize_action(value: Any) -> HookAction | None:
    text = str(value or "").strip().lower()
    if text in _VALID_ACTIONS:
        return text  # type: ignore[return-value]
    return None


def _normalize_failure_mode(value: Any) -> HookFailureMode | None:
    text = str(value or "").strip().lower()
    if text in _VALID_FAILURE_MODES:
        return text  # type: ignore[return-value]
    return None


def _normalize_timeout(value: Any) -> int:
    if isinstance(value, (int, float)):
        timeout = int(value)
        return timeout if timeout > 0 else DEFAULT_TIMEOUT_SECONDS
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            timeout = int(stripped)
            return timeout if timeout > 0 else DEFAULT_TIMEOUT_SECONDS
    return DEFAULT_TIMEOUT_SECONDS


def _normalize_event_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def _canonical_event_name(value: str) -> HookEventName | None:
    token = _normalize_event_token(value)
    if not token:
        return None
    return _EVENT_TOKEN_TO_INTERNAL.get(token)


def _claude_event_name(event: HookEventName) -> str:
    return _CLAUDE_EVENT_BY_INTERNAL.get(event, event)


def _decode_export_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        inner = value[1:-1]
        if value[0] == "'":
            # Support shell-escaped single quotes from hooks that append to CLAUDE_ENV_FILE.
            return inner.replace("'\"'\"'", "'")
        return inner.replace('\\"', '"').replace("\\$", "$")
    return value


def _load_exported_env(env_file: Path) -> dict[str, str]:
    if not env_file.exists() or not env_file.is_file():
        return {}
    loaded: dict[str, str] = {}
    try:
        content = env_file.read_text(encoding="utf-8")
    except Exception:
        return loaded
    for raw_line in content.splitlines():
        match = _EXPORT_PATTERN.match(raw_line)
        if not match:
            continue
        name = match.group(1)
        loaded[name] = _decode_export_value(match.group(2))
    return loaded


def _ensure_runtime_paths(cwd: str) -> tuple[Path, Path]:
    runtime_dir = (Path(cwd).resolve() / HOOKS_RUNTIME_DIR).resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)
    plugin_data_dir = runtime_dir / "plugin_data"
    plugin_data_dir.mkdir(parents=True, exist_ok=True)
    env_file = runtime_dir / "claude_env.sh"
    env_file.parent.mkdir(parents=True, exist_ok=True)
    if not env_file.exists():
        env_file.touch()
    return env_file, plugin_data_dir


def _build_hook_env(cwd: str, context: Mapping[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    env_file, plugin_data_dir = _ensure_runtime_paths(cwd)
    project_dir = str(Path(cwd).resolve())
    env.update(
        {
            "CLAUDE_PROJECT_DIR": project_dir,
            "CLAUDE_PLUGIN_ROOT": project_dir,
            "CLAUDE_PLUGIN_DATA": str(plugin_data_dir),
            "CLAUDE_ENV_FILE": str(env_file),
        }
    )

    explicit_map = {
        "claude_project_dir": "CLAUDE_PROJECT_DIR",
        "claude_plugin_root": "CLAUDE_PLUGIN_ROOT",
        "claude_plugin_data": "CLAUDE_PLUGIN_DATA",
        "claude_env_file": "CLAUDE_ENV_FILE",
    }
    for key, env_name in explicit_map.items():
        value = context.get(key)
        if value is None:
            continue
        rendered = str(value).strip()
        if rendered:
            env[env_name] = rendered

    resolved_env_file = Path(env["CLAUDE_ENV_FILE"]).expanduser()
    resolved_env_file.parent.mkdir(parents=True, exist_ok=True)
    if not resolved_env_file.exists():
        resolved_env_file.touch()
    env.update(_load_exported_env(resolved_env_file))

    env["RTE_PROJECT_DIR"] = env["CLAUDE_PROJECT_DIR"]
    env["RTE_PLUGIN_ROOT"] = env["CLAUDE_PLUGIN_ROOT"]
    env["RTE_PLUGIN_DATA"] = env["CLAUDE_PLUGIN_DATA"]
    return env


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _build_hook_stdin_payload(
    event: HookEventName, target: str, context: Mapping[str, Any]
) -> str:
    payload = {str(key): _json_safe(value) for key, value in context.items()}
    payload.setdefault("hook_event_name", _claude_event_name(event))
    payload.setdefault("rte_hook_event_name", event)
    payload.setdefault("target", target)
    return json.dumps(payload, ensure_ascii=False)


def _parse_hook_decision(stdout_text: str) -> tuple[bool, str | None, str | None]:
    stripped = stdout_text.strip()
    if not stripped:
        return False, None, None

    candidates: list[str] = [stripped]
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(lines) > 1:
        candidates.extend(reversed(lines))

    last_error: str | None = None
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = str(exc)
            continue

        if not isinstance(payload, Mapping):
            return False, None, None
        decision = str(payload.get("decision") or "").strip().lower()
        if decision != "block":
            return False, None, None
        reason = str(payload.get("reason") or "").strip()
        return True, reason or "Hook requested block.", None

    return False, None, last_error


def _render_template(template: str, variables: Mapping[str, Any]) -> str:
    rendered = template
    lookup = {key: _to_string(value) for key, value in variables.items()}

    def replace_brace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in lookup:
            return match.group(0)
        return lookup[key]

    def replace_dollar(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in lookup:
            return match.group(0)
        return lookup[key]

    rendered = _BRACE_PATTERN.sub(replace_brace, rendered)
    rendered = _DOLLAR_BRACE_PATTERN.sub(replace_dollar, rendered)
    rendered = _DOLLAR_PATTERN.sub(replace_dollar, rendered)
    return rendered


def _hook_name_from_path(path: Path, event_dir: Path) -> str:
    relative = path.relative_to(event_dir).with_suffix("")
    return ":".join(relative.parts)


def _parse_hook_file(
    path: Path, event: HookEventName, event_dir: Path
) -> tuple[HookDefinition | None, str | None]:
    content = _read_file(path)
    if not content:
        return None, "hook file is empty"

    frontmatter, body = parse_frontmatter(content)
    action = _normalize_action(frontmatter.get("action"))
    if action is None:
        return None, "frontmatter `action` must be one of: bash, prompt_append"

    on_failure = _normalize_failure_mode(
        frontmatter.get("on_failure") or frontmatter.get("on-failure")
    )
    if on_failure is None:
        return None, "frontmatter `on_failure` must be one of: continue, abort"

    command_raw = frontmatter.get("command")
    command = str(command_raw).strip() if isinstance(command_raw, str) else None
    template = body.strip()
    if action == "bash" and not command:
        return None, "frontmatter `command` is required for bash action"
    if action == "prompt_append" and not template:
        return None, "prompt_append hook requires non-empty markdown body"

    description_raw = frontmatter.get("description")
    description = (
        str(description_raw).strip()
        if isinstance(description_raw, str) and description_raw.strip()
        else _extract_title(template if action == "prompt_append" else command or "")
    )
    match_raw = frontmatter.get("match")
    match_pattern = (
        str(match_raw).strip() if isinstance(match_raw, str) and match_raw.strip() else "*"
    )
    timeout_seconds = _normalize_timeout(frontmatter.get("timeout"))

    definition = HookDefinition(
        event=event,
        name=_hook_name_from_path(path, event_dir),
        description=description,
        match=match_pattern,
        action=action,
        on_failure=on_failure,
        timeout_seconds=timeout_seconds,
        command=command,
        template=template,
        source_path=path,
    )
    return definition, None


def _load_hooks_json(
    hooks_root: Path,
    source_kind: str,
    hooks_by_event: dict[HookEventName, list[HookDefinition]],
    seen_keys: set[str],
    load_errors: list[str],
) -> None:
    hooks_json_path = hooks_root / HOOKS_JSON_FILE_NAME
    if not hooks_json_path.exists() or not hooks_json_path.is_file():
        return

    try:
        raw_payload = json.loads(hooks_json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        load_errors.append(
            f"[hooks] ignored invalid {source_kind} hooks file {hooks_json_path}: {exc}"
        )
        return

    hooks_payload = raw_payload.get("hooks") if isinstance(raw_payload, Mapping) else None
    if not isinstance(hooks_payload, Mapping):
        load_errors.append(
            f"[hooks] ignored invalid {source_kind} hooks file {hooks_json_path}: "
            "`hooks` object is required"
        )
        return

    for raw_event_name, groups in hooks_payload.items():
        if not isinstance(raw_event_name, str):
            load_errors.append(
                f"[hooks] ignored invalid {source_kind} hooks entry in {hooks_json_path}: "
                "event name must be string"
            )
            continue

        event = _canonical_event_name(raw_event_name)
        if event is None:
            load_errors.append(
                f"[hooks] ignored unsupported {source_kind} hooks event "
                f"`{raw_event_name}` in {hooks_json_path}"
            )
            continue

        if isinstance(groups, list):
            group_entries = groups
        elif isinstance(groups, Mapping):
            group_entries = [groups]
        else:
            load_errors.append(
                f"[hooks] ignored invalid {source_kind} hooks event "
                f"`{raw_event_name}` in {hooks_json_path}: expected array/object"
            )
            continue

        for group_index, group in enumerate(group_entries):
            if isinstance(group, Mapping):
                hooks_list = group.get("hooks")
                if isinstance(hooks_list, list):
                    command_entries = hooks_list
                elif isinstance(hooks_list, Mapping):
                    command_entries = [hooks_list]
                else:
                    load_errors.append(
                        f"[hooks] ignored invalid {source_kind} hooks group "
                        f"`{raw_event_name}[{group_index}]` in {hooks_json_path}: "
                        "`hooks` list is required"
                    )
                    continue
            elif isinstance(group, list):
                command_entries = group
            else:
                load_errors.append(
                    f"[hooks] ignored invalid {source_kind} hooks group "
                    f"`{raw_event_name}[{group_index}]` in {hooks_json_path}: "
                    "expected object/array"
                )
                continue

            for command_index, command_entry in enumerate(command_entries):
                if not isinstance(command_entry, Mapping):
                    load_errors.append(
                        f"[hooks] ignored invalid {source_kind} command hook "
                        f"`{raw_event_name}[{group_index}][{command_index}]` in "
                        f"{hooks_json_path}: expected object"
                    )
                    continue

                hook_type = str(command_entry.get("type") or "").strip().lower()
                if hook_type != "command":
                    load_errors.append(
                        f"[hooks] ignored unsupported {source_kind} hook type "
                        f"`{hook_type or '<empty>'}` in {hooks_json_path}"
                    )
                    continue

                command_raw = command_entry.get("command")
                command = str(command_raw).strip() if isinstance(command_raw, str) else ""
                if not command:
                    load_errors.append(
                        f"[hooks] ignored invalid {source_kind} command hook "
                        f"`{raw_event_name}[{group_index}][{command_index}]` in "
                        f"{hooks_json_path}: `command` is required"
                    )
                    continue

                timeout_seconds = _normalize_timeout(command_entry.get("timeout"))
                name_raw = command_entry.get("name")
                name = (
                    str(name_raw).strip()
                    if isinstance(name_raw, str) and str(name_raw).strip()
                    else f"json:{raw_event_name}:{group_index}:{command_index}"
                )
                relative_key = (
                    f"json:{_normalize_event_token(raw_event_name)}:{group_index}:{command_index}"
                )
                key = f"{event}:{relative_key}"
                if key in seen_keys:
                    continue

                hooks_by_event[event].append(
                    HookDefinition(
                        event=event,
                        name=name,
                        description=f"{raw_event_name} command hook",
                        match="*",
                        action="bash",
                        on_failure="continue",
                        timeout_seconds=timeout_seconds,
                        command=command,
                        template="",
                        source_path=hooks_json_path,
                        source="json",
                        pass_stdin_json=True,
                        parse_stdout_decision=True,
                    )
                )
                seen_keys.add(key)


def _load_hooks(cwd: str) -> tuple[dict[HookEventName, list[HookDefinition]], list[str]]:
    project_root = Path(cwd).resolve()
    roots = [
        ("project", project_root / PROJECT_HOOKS_DIR),
        ("user", env_root() / USER_HOOKS_DIR),
    ]
    hooks_by_event: dict[HookEventName, list[HookDefinition]] = {event: [] for event in HOOK_EVENTS}
    load_errors: list[str] = []
    seen_keys: set[str] = set()

    for source_kind, hooks_root in roots:
        for event in HOOK_EVENTS:
            aliases = HOOK_EVENT_DIR_ALIASES.get(event, (event,))
            for alias in aliases:
                event_dir = hooks_root / alias
                if not event_dir.exists() or not event_dir.is_dir():
                    continue

                for hook_file in sorted(event_dir.rglob("*.md")):
                    relative = hook_file.relative_to(event_dir).with_suffix("").as_posix().lower()
                    key = f"{event}:{relative}"
                    if key in seen_keys:
                        continue

                    definition, error = _parse_hook_file(hook_file, event, event_dir)
                    if definition is None:
                        load_errors.append(
                            f"[hooks] ignored invalid {source_kind} hook {hook_file}: {error}"
                        )
                        continue

                    hooks_by_event[event].append(definition)
                    seen_keys.add(key)

        _load_hooks_json(
            hooks_root=hooks_root,
            source_kind=source_kind,
            hooks_by_event=hooks_by_event,
            seen_keys=seen_keys,
            load_errors=load_errors,
        )

    return hooks_by_event, load_errors


def _match_target(pattern: str, target: str) -> bool:
    if not pattern:
        return True
    return fnmatch.fnmatch(target.lower(), pattern.lower())


def _truncate_debug(text: str, limit: int = 180) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit] + " ..."


async def _run_bash_hook(
    command: str,
    cwd: str,
    timeout_seconds: int,
    *,
    env: Mapping[str, str] | None = None,
    stdin_payload: str | None = None,
) -> HookCommandResult:
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=cwd,
        env=dict(env or os.environ.copy()),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdin_bytes = stdin_payload.encode("utf-8") if stdin_payload is not None else None
    try:
        stdout_raw, stderr_raw = await asyncio.wait_for(
            process.communicate(stdin_bytes), timeout=float(timeout_seconds)
        )
        return HookCommandResult(
            return_code=int(process.returncode or 0),
            stdout=stdout_raw.decode("utf-8", errors="replace"),
            stderr=stderr_raw.decode("utf-8", errors="replace"),
            timed_out=False,
        )
    except TimeoutError:
        process.kill()
        stdout_raw, stderr_raw = await process.communicate()
        return HookCommandResult(
            return_code=-1,
            stdout=stdout_raw.decode("utf-8", errors="replace"),
            stderr=stderr_raw.decode("utf-8", errors="replace"),
            timed_out=True,
        )


class HookRuntime:
    """Loads and executes hooks from project .agents/hooks and user ~/.env/hooks."""

    def __init__(self, cwd: str) -> None:
        self.cwd = str(Path(cwd).resolve())
        self._hooks_by_event, self._load_errors = _load_hooks(self.cwd)
        self._load_errors_reported = False

    def reload(self) -> None:
        """Reload hook files from disk."""
        self._hooks_by_event, self._load_errors = _load_hooks(self.cwd)
        self._load_errors_reported = False

    def hooks_for_event(self, event: HookEventName) -> list[HookDefinition]:
        return list(self._hooks_by_event.get(event, []))

    async def run(
        self,
        event: HookEventName,
        *,
        target: str,
        variables: Mapping[str, Any] | None = None,
        cwd: str | None = None,
        dev_mode: bool = False,
        allow_prompt_append: bool = True,
    ) -> HookExecutionOutcome:
        outcome = HookExecutionOutcome()
        hook_list = self._hooks_by_event.get(event, [])
        run_cwd = str(Path(cwd or self.cwd).resolve())
        context: dict[str, Any] = {
            "event": event,
            "target": target,
            "cwd": run_cwd,
        }
        if variables:
            context.update(variables)
        context.setdefault("session_id", "")
        context.setdefault("hook_event_name", _claude_event_name(event))
        context.setdefault("rte_hook_event_name", event)

        hook_env = _build_hook_env(run_cwd, context)
        hook_stdin_json = _build_hook_stdin_payload(event, target, context)

        if dev_mode and self._load_errors and not self._load_errors_reported:
            outcome.debug_lines.extend(self._load_errors)
            self._load_errors_reported = True

        if dev_mode:
            outcome.debug_lines.append(
                f"[dev] hooks {event}: target={target!r}, loaded={len(hook_list)}"
            )

        matched = 0
        for hook in hook_list:
            if not _match_target(hook.match, target):
                if dev_mode:
                    outcome.debug_lines.append(
                        f"[dev] hooks {event}/{hook.name}: skip match={hook.match!r}"
                    )
                continue

            matched += 1
            if dev_mode:
                outcome.debug_lines.append(
                    f"[dev] hooks {event}/{hook.name}: run action={hook.action}"
                )

            if hook.action == "prompt_append":
                if not allow_prompt_append:
                    if dev_mode:
                        outcome.debug_lines.append(
                            f"[dev] hooks {event}/{hook.name}: prompt_append ignored"
                        )
                    if hook.on_failure == "abort":
                        outcome.aborted = True
                        outcome.abort_reason = (
                            f"Hook {event}/{hook.name} aborted: prompt append is not allowed"
                        )
                        break
                    continue

                rendered = _render_template(hook.template, context).strip()
                if rendered:
                    outcome.prompt_appends.append(rendered)
                    if dev_mode:
                        outcome.debug_lines.append(
                            f"[dev] hooks {event}/{hook.name}: appended {len(rendered)} chars"
                        )
                elif dev_mode:
                    outcome.debug_lines.append(
                        f"[dev] hooks {event}/{hook.name}: rendered empty prompt"
                    )
                continue

            assert hook.command is not None
            command = _render_template(hook.command, context).strip()
            if not command:
                error_text = f"Hook {event}/{hook.name} failed: rendered command is empty"
                if dev_mode:
                    outcome.debug_lines.append(f"[dev] {error_text}")
                if hook.on_failure == "abort":
                    outcome.aborted = True
                    outcome.abort_reason = error_text
                    break
                continue

            command_result = await _run_bash_hook(
                command,
                run_cwd,
                hook.timeout_seconds,
                env=hook_env,
                stdin_payload=hook_stdin_json if hook.pass_stdin_json else None,
            )
            if command_result.timed_out:
                error_text = (
                    f"Hook {event}/{hook.name} timed out after {hook.timeout_seconds}s: {command}"
                )
                if dev_mode:
                    outcome.debug_lines.append(f"[dev] {error_text}")
                if hook.on_failure == "abort":
                    outcome.aborted = True
                    outcome.abort_reason = error_text
                    break
                continue

            if command_result.return_code != 0:
                error_text = (
                    f"Hook {event}/{hook.name} failed "
                    f"(exit {command_result.return_code}): {command}"
                )
                if dev_mode:
                    stderr_preview = _truncate_debug(command_result.stderr)
                    stdout_preview = _truncate_debug(command_result.stdout)
                    if stderr_preview:
                        outcome.debug_lines.append(
                            f"[dev] hooks {event}/{hook.name}: stderr={stderr_preview}"
                        )
                    if stdout_preview:
                        outcome.debug_lines.append(
                            f"[dev] hooks {event}/{hook.name}: stdout={stdout_preview}"
                        )
                    outcome.debug_lines.append(f"[dev] {error_text}")
                if hook.on_failure == "abort":
                    outcome.aborted = True
                    outcome.abort_reason = error_text
                    break
                continue

            if dev_mode:
                stdout_preview = _truncate_debug(command_result.stdout)
                outcome.debug_lines.append(
                    f"[dev] hooks {event}/{hook.name}: bash ok exit=0"
                )
                if stdout_preview:
                    outcome.debug_lines.append(
                        f"[dev] hooks {event}/{hook.name}: stdout={stdout_preview}"
                    )

            if hook.parse_stdout_decision:
                blocked, reason, parse_error = _parse_hook_decision(command_result.stdout)
                if parse_error and dev_mode:
                    outcome.debug_lines.append(
                        f"[dev] hooks {event}/{hook.name}: invalid decision JSON ({parse_error})"
                    )
                if blocked:
                    outcome.aborted = True
                    decision_reason = reason or "no reason provided"
                    outcome.abort_reason = (
                        f"Hook {event}/{hook.name} blocked execution: {decision_reason}"
                    )
                    break

        if dev_mode:
            outcome.debug_lines.append(f"[dev] hooks {event}: matched={matched}")

        return outcome
