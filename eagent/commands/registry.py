"""Slash command registry."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eagent.context.memory import load_agent_memory
from eagent.context.session_store import list_sessions
from eagent.context.token_counting import estimate_message_tokens
from eagent.core.types import CommandContext, SlashCommand
from eagent.paths import env_root
from eagent.skills.loader import parse_frontmatter
from eagent.skills.skill_tool import get_loaded_skills, initialize_skills


class ReloadRequested(Exception):
    """Signal that interactive CLI should restart in dev mode."""


@dataclass
class _Command:
    name: str
    description: str
    handler: Callable[[str, CommandContext], Awaitable[str | None]]
    argument_hint: str = ""
    examples: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)

    async def execute(self, args: str, context: CommandContext) -> str | None:
        return await self.handler(args, context)


PROJECT_COMMANDS_DIR = Path(".agents") / "commands"
USER_COMMANDS_DIR = Path("commands")
CUSTOM_COMMAND_SEGMENT_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass(frozen=True)
class _CustomCommandDefinition:
    name: str
    description: str
    argument_hint: str
    template: str
    source_path: Path


def _read_file_text(path: Path) -> str | None:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return None
    stripped = content.strip()
    return stripped if stripped else None


def _command_search_roots(cwd: str) -> list[Path]:
    project_root = Path(cwd).resolve()
    roots = [project_root / PROJECT_COMMANDS_DIR, env_root() / USER_COMMANDS_DIR]
    deduped: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if root in seen:
            continue
        seen.add(root)
        deduped.append(root)
    return deduped


def _valid_custom_segment(name: str) -> bool:
    return bool(name and CUSTOM_COMMAND_SEGMENT_PATTERN.fullmatch(name))


def _build_custom_command_name(command_file: Path, commands_dir: Path) -> str | None:
    relative = command_file.relative_to(commands_dir).with_suffix("")
    parts = [part.strip() for part in relative.parts]
    if not parts or any(not _valid_custom_segment(part) for part in parts):
        return None
    return ":".join(parts)


def _extract_markdown_title(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        return stripped[:80]
    return "User-defined command"


def _expand_command_template(template: str, args: str) -> str:
    rendered = template.replace("$ARGUMENTS", args.strip())
    tokens = args.split()
    for index in range(1, 10):
        value = tokens[index - 1] if index - 1 < len(tokens) else ""
        rendered = rendered.replace(f"${index}", value)
    return rendered.strip()


def _parse_custom_command_file(
    command_file: Path, commands_dir: Path
) -> _CustomCommandDefinition | None:
    command_name = _build_custom_command_name(command_file, commands_dir)
    if command_name is None:
        return None

    content = _read_file_text(command_file)
    if not content:
        return None

    frontmatter, body = parse_frontmatter(content)
    template = body.strip()
    if not template:
        return None

    description_raw = frontmatter.get("description")
    argument_hint_raw = frontmatter.get("argument-hint")
    description = (
        str(description_raw).strip()
        if isinstance(description_raw, str) and description_raw.strip()
        else _extract_markdown_title(template)
    )
    argument_hint = (
        str(argument_hint_raw).strip()
        if isinstance(argument_hint_raw, str) and argument_hint_raw.strip()
        else ""
    )
    return _CustomCommandDefinition(
        name=command_name,
        description=description,
        argument_hint=argument_hint,
        template=template,
        source_path=command_file,
    )


def _builtin_names_and_aliases() -> set[str]:
    names: set[str] = set()
    for command in _COMMANDS:
        names.add(command.name.lower())
        names.update(alias.lower() for alias in command.aliases)
    return names


def _load_custom_command_definitions(cwd: str) -> list[_CustomCommandDefinition]:
    blocked = _builtin_names_and_aliases()
    discovered: dict[str, _CustomCommandDefinition] = {}

    for root in _command_search_roots(cwd):
        commands_dir = root
        if not commands_dir.exists() or not commands_dir.is_dir():
            continue
        for command_file in sorted(commands_dir.rglob("*.md")):
            definition = _parse_custom_command_file(command_file, commands_dir)
            if definition is None:
                continue
            key = definition.name.lower()
            if key in blocked or key in discovered:
                continue
            discovered[key] = definition
    return list(discovered.values())


def _resolve_custom_command(cwd: str, command_name: str) -> _CustomCommandDefinition | None:
    lookup = command_name.strip().lower()
    if not lookup:
        return None
    for definition in _load_custom_command_definitions(cwd):
        if definition.name.lower() == lookup:
            return definition
    return None


async def _execute_custom_markdown_command(
    command_name: str, args: str, ctx: CommandContext
) -> str | None:
    definition = _resolve_custom_command(ctx.cwd, command_name)
    if definition is None:
        return f"Unknown command: /{command_name}. Use /help."

    prompt = _expand_command_template(definition.template, args)
    if not prompt:
        return f"Custom command /{definition.name} rendered empty prompt."

    cwd_path = Path(ctx.cwd).resolve()
    source = (
        str(definition.source_path.relative_to(cwd_path))
        if definition.source_path.is_relative_to(cwd_path)
        else str(definition.source_path)
    )
    mode = (
        "interactive-insert"
        if ctx.interactive and ctx.set_input_draft is not None
        else "queued-send"
    )

    def _with_dev_logs(message: str) -> str:
        if not ctx.dev_mode:
            return message
        debug_lines = [
            "[dev] custom command debug",
            f"- name: /{definition.name}",
            f"- source: {source}",
            f"- args: {args!r}",
            f"- mode: {mode}",
            f"- template_chars: {len(definition.template)}",
            f"- rendered_chars: {len(prompt)}",
        ]
        return message + "\n" + "\n".join(debug_lines)

    if ctx.interactive and ctx.set_input_draft is not None:
        ctx.set_input_draft(prompt)
        return _with_dev_logs(
            f"Inserted custom command /{definition.name} into input from {source}."
        )

    ctx.send_prompt(prompt)
    return _with_dev_logs(f"Queued custom command /{definition.name} from {source}.")


def _load_custom_commands(cwd: str) -> list[_Command]:
    commands: list[_Command] = []
    for definition in _load_custom_command_definitions(cwd):

        async def _handler(
            args: str,
            ctx: CommandContext,
            command_name: str = definition.name,
        ) -> str | None:
            return await _execute_custom_markdown_command(command_name, args, ctx)

        commands.append(
            _Command(
                name=definition.name,
                description=definition.description,
                handler=_handler,
                argument_hint=definition.argument_hint,
                examples=[f"/{definition.name}"],
            )
        )
    return commands


async def _help(_args: str, ctx: CommandContext) -> str:
    lines = ["Available commands:", ""]
    for command in get_commands(ctx.cwd):
        aliases = f" ({', '.join(command.aliases)})" if command.aliases else ""
        lines.append(f"  /{command.name.ljust(12)} {command.description}{aliases}")
    lines.append("")
    lines.append("Type a normal message to run the agent.")
    return "\n".join(lines)


async def _compact(_args: str, ctx: CommandContext) -> str:
    if not ctx.messages:
        return "Nothing to compact."
    await ctx.compact()
    return "Compaction completed."


async def _clear(_args: str, ctx: CommandContext) -> str:
    ctx.clear_messages()
    return "Conversation cleared."


async def _model(args: str, ctx: CommandContext) -> str:
    value = args.strip()
    if value:
        try:
            changed = ctx.set_model(value)
        except ValueError as exc:
            return str(exc)
        return f"Model changed to: {changed}"
    return f"Current model: {ctx.model_config.model}"


async def _agent(_args: str, _ctx: CommandContext) -> str:
    return "Use /agent in TUI to open the model picker, or /model <name> to switch directly."


async def _cost(_args: str, ctx: CommandContext) -> str:
    tracker = ctx.cost_tracker
    config = ctx.model_config
    return "\n".join(
        [
            f"Model:    {config.model}",
            f"Turns:    {tracker.turns}",
            f"Input:    {tracker.total_input_tokens:,}",
            f"Output:   {tracker.total_output_tokens:,}",
            f"Cache R:  {tracker.total_cache_read_tokens:,}",
            f"Cache W:  {tracker.total_cache_creation_tokens:,}",
            f"Cost:     ${tracker.total_cost_usd(config):.4f}",
        ]
    )


async def _resume(args: str, ctx: CommandContext) -> str:
    session_prefix = args.strip().lower()
    sessions = await list_sessions()
    if not session_prefix:
        if not sessions:
            return "No previous sessions found."
        lines = ["Recent sessions:", ""]
        for session in sessions[:10]:
            lines.append(
                "  "
                f"{session.get('id', '')[:8]}  "
                f"{session.get('cwd', '')} "
                f"({session.get('messageCount', 0)} msgs)"
            )
        lines.append("\nUse /resume <session-prefix> to resume.")
        return "\n".join(lines)

    match = next(
        (s for s in sessions if str(s.get("id", "")).lower().startswith(session_prefix)), None
    )
    if not match:
        return f'No session found matching "{session_prefix}".'

    error = await ctx.resume_session(str(match["id"]))
    if error:
        return error
    return f"Resumed session {str(match['id'])[:8]} ({match.get('messageCount', 0)} messages)."


async def _new(_args: str, ctx: CommandContext) -> str:
    if ctx.new_session is None:
        ctx.clear_messages()
        return "Started a new empty context."
    new_session_id = await ctx.new_session()
    return f"Started new session {new_session_id[:8]} with empty context."


async def _plan(_args: str, ctx: CommandContext) -> str:
    if ctx.permission_mode == "plan":
        ctx.set_permission_mode("default")
        return "Plan mode disabled."
    ctx.set_permission_mode("plan")
    return "Plan mode enabled (read-only)."


async def _memory(_args: str, ctx: CommandContext) -> str:
    content = await load_agent_memory(ctx.cwd)
    if not content:
        return "No memory file found."
    if len(content) > 3000:
        return content[:3000] + f"\n\n... ({len(content)} chars total)"
    return content


async def _config(_args: str, ctx: CommandContext) -> str:
    return "\n".join(
        [
            f"Model:       {ctx.model_config.model}",
            f"Context:     {ctx.model_config.context_window:,}",
            f"Max output:  {ctx.model_config.max_output_tokens:,}",
            f"Mode:        {ctx.permission_mode}",
            f"CWD:         {ctx.cwd}",
            f"Session:     {ctx.session_id[:8]}",
            f"Tools:       {len(ctx.tools)} loaded",
        ]
    )


async def _status(_args: str, ctx: CommandContext) -> str:
    token_count = estimate_message_tokens(ctx.messages)
    threshold = ctx.model_config.context_window - ctx.model_config.max_output_tokens - 13_000
    pct = int((token_count / threshold) * 100) if threshold > 0 else 0
    return "\n".join(
        [
            f"Session:    {ctx.session_id[:8]}",
            f"Model:      {ctx.model_config.model}",
            f"Messages:   {len(ctx.messages)}",
            f"Tokens:     {token_count:,} / {threshold:,} ({pct}%)",
            f"Mode:       {ctx.permission_mode}",
            f"CWD:        {ctx.cwd}",
            f"Files mod:  {len(ctx.file_history.tracked_files)}",
            f"Snapshots:  {len(ctx.file_history.snapshots)}",
        ]
    )


async def _skills(_args: str, ctx: CommandContext) -> str:
    skills = get_loaded_skills()
    if not skills:
        await initialize_skills(ctx.cwd)
        skills = get_loaded_skills()
    if not skills:
        return "No skills loaded. Place skills in .agents/skills, ~/.agents/skills, or ~/.env/skills."
    lines = ["Available skills:", ""]
    for skill in skills:
        lines.append(f"  {skill.name}  {skill.description}")
    return "\n".join(lines)


async def _context(_args: str, ctx: CommandContext) -> str:
    token_count = estimate_message_tokens(ctx.messages)
    context_window = ctx.model_config.context_window
    max_output = ctx.model_config.max_output_tokens
    usable = context_window - max_output - 13_000
    pct = min(100, int((token_count / usable) * 100)) if usable > 0 else 0
    return "\n".join(
        [
            f"Context Usage  {ctx.model_config.model}",
            f"Usage: {pct}%",
            f"Total: {token_count:,} / {usable:,} (window: {context_window:,})",
        ]
    )


async def _exit(_args: str, _ctx: CommandContext) -> str:
    raise SystemExit(0)


async def _reload(_args: str, ctx: CommandContext) -> str:
    if not ctx.dev_mode:
        return "Reload is only available in dev mode. Restart in dev mode with `--dev`."
    raise ReloadRequested()


_COMMANDS: list[_Command] = [
    _Command("help", "Show available commands", _help, examples=["/help"], aliases=["h", "?"]),
    _Command("compact", "Compact conversation context", _compact),
    _Command("clear", "Clear conversation history", _clear, aliases=["reset"]),
    _Command(
        "model",
        "Show or change model",
        _model,
        argument_hint="<name|alias>",
        examples=["/model kimi", "/model minimax"],
        aliases=["m"],
    ),
    _Command("agent", "Open model picker (TUI)", _agent, examples=["/agent"]),
    _Command("cost", "Show token usage and cost", _cost),
    _Command(
        "resume",
        "Resume a previous session",
        _resume,
        argument_hint="<session-prefix>",
        examples=["/resume ab12cd34"],
        aliases=["r"],
    ),
    _Command("new", "Create a new empty context/session", _new, examples=["/new"], aliases=["n"]),
    _Command("plan", "Toggle plan mode (read-only)", _plan),
    _Command("memory", "Show memory files", _memory),
    _Command("config", "Show current configuration", _config),
    _Command("status", "Show session status", _status),
    _Command("skills", "List available skills", _skills),
    _Command("context", "Show context window usage", _context, aliases=["ctx"]),
    _Command(
        "reload",
        "Reload RTE-AI process (dev mode)",
        _reload,
        examples=["/reload"],
    ),
    _Command("exit", "Exit RTE-AI", _exit, aliases=["quit", "q"]),
]


def get_commands(cwd: str | None = None) -> list[SlashCommand]:
    commands: list[_Command] = list(_COMMANDS)
    if cwd:
        commands.extend(_load_custom_commands(cwd))
    return list(commands)


def get_command_info_list(cwd: str | None = None) -> list[dict[str, Any]]:
    return [
        {
            "name": command.name,
            "description": command.description,
            "argument_hint": command.argument_hint,
            "examples": list(command.examples),
            "aliases": list(command.aliases),
        }
        for command in get_commands(cwd)
    ]


async def execute_command(command_line: str, context: CommandContext) -> str | None:
    if not command_line.startswith("/"):
        return None
    raw = command_line[1:].strip()
    if not raw:
        return None

    parts = raw.split(maxsplit=1)
    command_name = parts[0]
    args = parts[1] if len(parts) > 1 else ""

    command = next(
        (
            c
            for c in get_commands(context.cwd)
            if c.name == command_name or command_name in c.aliases
        ),
        None,
    )
    if command is None:
        return f"Unknown command: /{command_name}. Use /help."
    return await command.execute(args, context)
