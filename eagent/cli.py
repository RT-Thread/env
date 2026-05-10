"""eagent CLI entrypoint."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from eagent.commands.registry import ReloadRequested, execute_command, get_command_info_list
from eagent.context.agent_config import (
    AgentProfile,
    AgentProfileSet,
    load_agent_profiles,
    set_active_profile,
)
from eagent.context.compaction import CompactParams
from eagent.context.compaction import compact as compact_messages
from eagent.context.git_context import get_git_context
from eagent.context.memory import load_agent_memory
from eagent.context.session_store import (
    init_session,
    list_session_summaries_sync,
    load_session,
    save_message,
)
from eagent.core.agent_loop import agent_loop
from eagent.core.api_client import call_model, get_model_config
from eagent.core.types import (
    CommandContext,
    Message,
    PermissionDecision,
    PermissionMode,
    QueryParams,
    SystemPromptBlock,
    TextBlock,
)
from eagent.files.cache import create_file_state_cache
from eagent.files.history import create_file_history_state
from eagent.hooks import HookRuntime
from eagent.hooks.runtime import HookEventName
from eagent.mcp.manager import initialize_mcp_servers, shutdown_mcp_servers
from eagent.paths import env_root
from eagent.prompt.system_prompt import build_system_prompt_blocks
from eagent.reload import ReloadArgs
from eagent.skills.skill_tool import set_skill_query_params
from eagent.tools.agent_tool import set_agent_query_params
from eagent.tools.registry import initialize_tools, register_dynamic_tools
from eagent.tui.app import EnvAgentTui
from eagent.tui.status_bar import StatusMeta
from eagent.utils.completer import ResumeSuggestion, build_completer
from eagent.utils.cost import create_cost_tracker, summarize_cost
from eagent.utils.streaming import event_to_log_line


@dataclass
class CliState:
    api_key: str
    cwd: str
    model_name: str
    permission_mode: PermissionMode
    enable_thinking: bool
    thinking_budget: int | None
    max_turns: int
    enable_mcp: bool
    dev_mode: bool

    session_id: str = ""
    model_config: Any = None
    tools: list[Any] = None
    messages: list[Message] = None
    read_file_state: Any = None
    file_history: Any = None
    cost_tracker: Any = None
    system_prompt_blocks: list[Any] = None
    profile_set: AgentProfileSet | None = None
    active_profile: AgentProfile | None = None
    api_base_url: str | None = None
    reload_requested: bool = False
    hook_runtime: HookRuntime | None = None
    session_hooks_ran: bool = False
    session_end_hooks_ran: bool = False

    def __post_init__(self) -> None:
        self.session_id = self.session_id or str(uuid.uuid4())
        self.model_config = get_model_config(self.model_name)
        self.tools = []
        self.messages = []
        self.read_file_state = create_file_state_cache()
        self.file_history = create_file_history_state()
        self.cost_tracker = create_cost_tracker()
        self.system_prompt_blocks = []

    def apply_profile(self, profile: AgentProfile) -> str:
        self.active_profile = profile
        self.model_config = get_model_config(profile.model)
        self.api_key = profile.key
        self.api_base_url = profile.base_url
        return profile.name

    def set_model_value(self, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Model name cannot be empty.")

        if self.profile_set and self.profile_set.profiles:
            matched = next((p for p in self.profile_set.profiles if p.name == normalized), None)
            if matched:
                self.profile_set = set_active_profile(matched.name, self.profile_set)
                self.apply_profile(matched)
                return f"{matched.name} ({matched.model})"

        self.active_profile = None
        self.model_config = get_model_config(normalized)
        return self.model_config.model


async def _default_permission_request(tool: str, _input: Any, message: str) -> PermissionDecision:
    response = await asyncio.to_thread(click.confirm, f"Allow {tool}? {message}", default=False)
    if response:
        return PermissionDecision(behavior="allow")
    return PermissionDecision(behavior="deny", message=f"Denied by user for {tool}")


async def _compact_call_model(
    system_prompt: str,
    prompt: str,
    model: str,
    api_key: str,
    api_base_url: str | None,
) -> str:
    synthetic = Message(role="user", content=[TextBlock(type="text", text=prompt)])
    model_config = get_model_config(model)
    chunks: list[str] = []
    async for event in call_model(
        messages=[synthetic],
        tools=[],
        model_config=model_config,
        system_prompt_blocks=[SystemPromptBlock(type="text", text=system_prompt)],
        api_key=api_key,
        api_base_url=api_base_url,
    ):
        if event["type"] == "assistant_text":
            chunks.append(event["text"])
    return "".join(chunks)


async def _manual_compact(state: CliState) -> None:
    if not state.messages:
        return

    async def _call(system_prompt: str, prompt: str, model: str, api_key: str) -> str:
        return await _compact_call_model(
            system_prompt,
            prompt,
            model,
            api_key,
            state.api_base_url,
        )

    result = await compact_messages(
        state.messages,
        CompactParams(
            api_key=state.api_key,
            model=state.model_config.model,
            system_prompt_blocks=state.system_prompt_blocks,
        ),
        _call,
    )
    state.messages = result.compacted


async def _resume_session(state: CliState, session_id: str) -> str | None:
    loaded = await load_session(session_id)
    if not loaded:
        return f"Session {session_id} has no transcript or does not exist."
    state.session_id = session_id
    state.messages = loaded
    return None


async def _new_session(state: CliState) -> str:
    state.session_id = str(uuid.uuid4())
    state.messages.clear()
    state.read_file_state = create_file_state_cache()
    state.file_history = create_file_history_state()
    await init_session(state.session_id, state.cwd)
    state.session_hooks_ran = False
    state.session_end_hooks_ran = False
    return state.session_id


def _message_with_user_text(text: str) -> Message:
    return Message(role="user", content=[TextBlock(type="text", text=text)], id=str(uuid.uuid4()))


def _last_assistant_message(messages: list[Message]) -> str:
    for message in reversed(messages):
        if message.role != "assistant":
            continue
        chunks: list[str] = []
        for block in message.content:
            if isinstance(block, TextBlock):
                text = block.text.strip()
                if text:
                    chunks.append(text)
        if chunks:
            return "\n".join(chunks).strip()
    return ""


def _emit_hook_debug_lines(
    lines: list[str],
    *,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
    output_sink: Callable[[str], None] | None = None,
) -> None:
    if not lines:
        return
    for line in lines:
        event = {"type": "hook_debug", "text": line}
        if event_sink is not None:
            event_sink(event)
        elif output_sink is not None:
            output_sink(line)
        else:
            click.echo(line)


def _emit_hook_message(
    message: str,
    *,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
    output_sink: Callable[[str], None] | None = None,
) -> None:
    if event_sink is not None:
        event_sink({"type": "error", "error": Exception(message)})
        return
    if output_sink is not None:
        output_sink(message)
        return
    click.echo(message, err=True)


async def _run_cli_hook_event(
    state: CliState,
    *,
    event: HookEventName,
    target: str,
    variables: dict[str, Any] | None = None,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
    output_sink: Callable[[str], None] | None = None,
) -> tuple[bool, list[str]]:
    runtime = state.hook_runtime
    if runtime is None:
        return False, []

    payload: dict[str, Any] = {
        "session_id": state.session_id,
        "cwd": state.cwd,
    }
    if variables:
        payload.update(variables)

    outcome = await runtime.run(
        event,
        target=target,
        variables=payload,
        cwd=state.cwd,
        dev_mode=state.dev_mode,
    )
    _emit_hook_debug_lines(outcome.debug_lines, event_sink=event_sink, output_sink=output_sink)

    if outcome.aborted:
        reason = outcome.abort_reason or f"Hook {event} aborted."
        _emit_hook_message(reason, event_sink=event_sink, output_sink=output_sink)
        return True, outcome.prompt_appends

    return False, outcome.prompt_appends


async def _ensure_session_start_hooks(
    state: CliState,
    *,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
    output_sink: Callable[[str], None] | None = None,
) -> tuple[bool, list[str]]:
    if state.session_hooks_ran:
        return False, []

    state.session_hooks_ran = True
    return await _run_cli_hook_event(
        state,
        event="session_start",
        target=state.session_id,
        variables={"session_id": state.session_id},
        event_sink=event_sink,
        output_sink=output_sink,
    )


async def _run_session_end_hooks(
    state: CliState,
    *,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
    output_sink: Callable[[str], None] | None = None,
) -> tuple[bool, list[str]]:
    if state.session_end_hooks_ran:
        return False, []
    state.session_end_hooks_ran = True
    return await _run_cli_hook_event(
        state,
        event="session_end",
        target=state.session_id,
        variables={"session_id": state.session_id},
        event_sink=event_sink,
        output_sink=output_sink,
    )


async def _build_state(
    api_key: str,
    model: str,
    cwd: str,
    permission_mode: PermissionMode,
    enable_thinking: bool,
    thinking_budget: int | None,
    max_turns: int,
    enable_mcp: bool,
    dev_mode: bool,
    session_id: str | None,
) -> CliState:
    state = CliState(
        api_key=api_key,
        cwd=cwd,
        model_name=model,
        permission_mode=permission_mode,
        enable_thinking=enable_thinking,
        thinking_budget=thinking_budget,
        max_turns=max_turns,
        enable_mcp=enable_mcp,
        dev_mode=dev_mode,
    )

    state.profile_set = load_agent_profiles()
    if state.profile_set.active:
        state.apply_profile(state.profile_set.active)

    if model and model != "sonnet":
        state.set_model_value(model)

    if session_id:
        state.session_id = session_id
        state.messages = await load_session(session_id)
    else:
        await init_session(state.session_id, cwd)

    agent_memory = await load_agent_memory(cwd)
    git_context = await get_git_context(cwd)
    state.system_prompt_blocks = build_system_prompt_blocks(
        agent_memory, git_context, cwd, state.model_config.model
    )

    state.tools = await initialize_tools(cwd)
    if enable_mcp:
        mcp_tools = await initialize_mcp_servers(cwd)
        if mcp_tools:
            register_dynamic_tools(mcp_tools)
            state.tools.extend(mcp_tools)

    state.hook_runtime = HookRuntime(cwd)

    return state


async def _run_agent_prompt(
    state: CliState,
    prompt: str,
    text_sink: Callable[[str], None] | None = None,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
    on_permission_request: Callable[[str, Any, str], Awaitable[PermissionDecision]] | None = None,
) -> None:
    before = len(state.messages)
    session_aborted, session_prompts = await _ensure_session_start_hooks(
        state,
        event_sink=event_sink,
    )
    if session_aborted:
        return
    for extra_prompt in session_prompts:
        if extra_prompt.strip():
            state.messages.append(_message_with_user_text(extra_prompt))

    prompt_text = prompt.strip()
    prompt_target = prompt_text if prompt_text else "(empty)"
    user_aborted, user_prompts = await _run_cli_hook_event(
        state,
        event="user_prompt_submit",
        target=prompt_target,
        variables={
            "prompt": prompt,
            "prompt_text": prompt_text,
        },
        event_sink=event_sink,
    )
    if user_aborted:
        return
    for extra_prompt in user_prompts:
        if extra_prompt.strip():
            state.messages.append(_message_with_user_text(extra_prompt))

    state.messages.append(_message_with_user_text(prompt))

    params = QueryParams(
        messages=state.messages,
        tools=state.tools,
        model_config=state.model_config,
        system_prompt_blocks=state.system_prompt_blocks,
        max_turns=state.max_turns,
        permission_mode=state.permission_mode,
        api_key=state.api_key,
        api_base_url=state.api_base_url,
        cwd=state.cwd,
        session_id=state.session_id,
        on_permission_request=on_permission_request or _default_permission_request,
        enable_thinking=state.enable_thinking,
        thinking_budget=state.thinking_budget,
        read_file_state=state.read_file_state,
        file_history=state.file_history,
        hook_runtime=state.hook_runtime,
        dev_mode=state.dev_mode,
    )

    set_agent_query_params(params)
    set_skill_query_params(params)

    printed_text = False
    stop_target = "turn_complete"
    stop_error = ""
    async for event in agent_loop(params):
        event_type = event["type"]
        if event_type == "assistant_text":
            if text_sink is not None:
                text_sink(event["text"])
            else:
                click.echo(event["text"], nl=False)
                printed_text = True
        elif event_type == "usage":
            state.cost_tracker.add(event["usage"])
        elif event_type == "error":
            stop_target = "error"
            stop_error = str(event.get("error") or "")
            if event_sink is not None:
                event_sink(event)
            elif printed_text:
                click.echo()
                printed_text = False
            if text_sink is None:
                click.echo(f"Error: {event.get('error')}", err=True)
        elif event_type in {
            "tool_start",
            "tool_result",
            "compact",
            "max_turns_reached",
            "turn_complete",
            "hook_debug",
        }:
            if event_type == "turn_complete":
                stop_target = str(event.get("stop_reason") or "turn_complete")
            elif event_type == "max_turns_reached":
                stop_target = f"max_turns:{event.get('max_turns')}"
            if event_sink is not None:
                event_sink(event)
            elif printed_text:
                click.echo()
                printed_text = False
                click.echo(event_to_log_line(event))
            elif text_sink is None:
                click.echo(event_to_log_line(event))

    if printed_text and text_sink is None:
        click.echo()

    stop_aborted, stop_prompts = await _run_cli_hook_event(
        state,
        event="stop",
        target=stop_target,
        variables={
            "stop_reason": stop_target,
            "error": stop_error,
            "last_assistant_message": _last_assistant_message(state.messages),
        },
        event_sink=event_sink,
    )
    if not stop_aborted:
        for extra_prompt in stop_prompts:
            if extra_prompt.strip():
                state.messages.append(_message_with_user_text(extra_prompt))

    for message in state.messages[before:]:
        await save_message(state.session_id, message, cwd=state.cwd)


async def _run_command(
    state: CliState,
    command_line: str,
    output_sink: Callable[[str], None] | None = None,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
    text_sink: Callable[[str], None] | None = None,
    on_permission_request: Callable[[str, Any, str], Awaitable[PermissionDecision]] | None = None,
    set_input_draft: Callable[[str], None] | None = None,
    interactive: bool = False,
) -> bool:
    pending_prompt: list[str] = []

    raw = command_line[1:].strip() if command_line.startswith("/") else ""
    command_name = ""
    command_args = ""
    if raw:
        parts = raw.split(maxsplit=1)
        command_name = parts[0]
        command_args = parts[1] if len(parts) > 1 else ""

    session_aborted, session_prompts = await _ensure_session_start_hooks(
        state,
        event_sink=event_sink,
        output_sink=output_sink,
    )
    pending_prompt.extend(session_prompts)
    if session_aborted:
        return False

    if command_name:
        before_aborted, before_prompts = await _run_cli_hook_event(
            state,
            event="before_command",
            target=command_name,
            variables={
                "command_name": command_name,
                "command_args": command_args,
                "command_line": command_line,
            },
            event_sink=event_sink,
            output_sink=output_sink,
        )
        pending_prompt.extend(before_prompts)
        if before_aborted:
            return False

    command_context = CommandContext(
        messages=state.messages,
        tools=state.tools,
        model_config=state.model_config,
        cwd=state.cwd,
        session_id=state.session_id,
        cost_tracker=state.cost_tracker,
        file_history=state.file_history,
        read_file_state=state.read_file_state,
        permission_mode=state.permission_mode,
        set_permission_mode=lambda mode: setattr(state, "permission_mode", mode),
        set_model=lambda model: state.set_model_value(model),
        clear_messages=lambda: state.messages.clear(),
        compact=lambda: _manual_compact(state),
        resume_session=lambda sid: _resume_session(state, sid),
        send_prompt=lambda text: pending_prompt.append(text),
        set_input_draft=set_input_draft,
        interactive=interactive,
        new_session=lambda: _new_session(state),
        dev_mode=state.dev_mode,
    )

    command_result: str | None = None
    command_error: Exception | None = None

    try:
        command_result = await execute_command(command_line, command_context)
    except SystemExit:
        return True
    except ReloadRequested:
        state.reload_requested = True
        return True
    except Exception as exc:
        command_error = exc

    if command_error is not None:
        on_error_aborted, on_error_prompts = await _run_cli_hook_event(
            state,
            event="on_error",
            target=command_name or "command",
            variables={
                "command_name": command_name,
                "command_args": command_args,
                "command_line": command_line,
                "error": str(command_error),
                "source": "command",
            },
            event_sink=event_sink,
            output_sink=output_sink,
        )
        pending_prompt.extend(on_error_prompts)
        message = f"Command error: {command_error}"
        if output_sink is not None:
            output_sink(message)
        else:
            click.echo(message, err=True)
        if on_error_aborted:
            return False
    else:
        if command_result:
            if output_sink is not None:
                output_sink(command_result)
            else:
                click.echo(command_result)

        if command_name:
            after_aborted, after_prompts = await _run_cli_hook_event(
                state,
                event="after_command",
                target=command_name,
                variables={
                    "command_name": command_name,
                    "command_args": command_args,
                    "command_line": command_line,
                    "result": command_result or "",
                },
                event_sink=event_sink,
                output_sink=output_sink,
            )
            pending_prompt.extend(after_prompts)
            if after_aborted:
                return False

    while pending_prompt:
        prompt = pending_prompt.pop(0)
        await _run_agent_prompt(
            state,
            prompt,
            text_sink=text_sink,
            event_sink=event_sink,
            on_permission_request=on_permission_request,
        )

    return False


def _status_bar(value: int, budget: int, width: int = 10) -> str:
    if budget <= 0:
        return "[" + "?" * width + "]"
    ratio = max(0.0, min(1.0, value / budget))
    filled = int(round(ratio * width))
    if filled > width:
        filled = width
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _git_branch_status(cwd: str) -> str:
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.2,
            check=False,
        )
    except Exception:
        return ""
    if branch.returncode != 0:
        return ""
    value = branch.stdout.strip()
    return value if value and value != "HEAD" else ""


def _status_meta(state: CliState) -> StatusMeta:
    provider = state.active_profile.provider if state.active_profile else "anthropic"
    return StatusMeta(
        model=f"{provider}/{state.model_config.model}",
        cwd=state.cwd,
        git=_git_branch_status(state.cwd),
    )


def _build_tui_startup_messages(state: CliState) -> list[str]:
    messages: list[str] = []
    if state.profile_set and state.profile_set.load_error:
        messages.append(state.profile_set.load_error)

    if not state.api_key and os.environ.get("ENV_AGENT_MOCK", "").lower() not in {"1", "true", "yes"}:
        messages.append(
            "No active API key found. Configure ~/.env/agent.json or ANTHROPIC_API_KEY."
        )
    return messages


async def _interactive_loop(state: CliState) -> None:
    permission_request: Callable[[str, Any, str], Awaitable[PermissionDecision]] = (
        _default_permission_request
    )
    input_draft_setter: Callable[[str], None] | None = None

    async def _on_prompt(
        text: str,
        assistant_sink: Callable[[str], None],
        event_sink: Callable[[dict[str, Any]], None],
    ) -> None:
        await _run_agent_prompt(
            state,
            text,
            text_sink=assistant_sink,
            event_sink=event_sink,
            on_permission_request=permission_request,
        )

    async def _on_command(
        command_line: str,
        output_sink: Callable[[str], None],
        event_sink: Callable[[dict[str, Any]], None],
    ) -> bool:
        return await _run_command(
            state,
            command_line,
            output_sink=output_sink,
            event_sink=event_sink,
            text_sink=output_sink,
            on_permission_request=permission_request,
            set_input_draft=input_draft_setter,
            interactive=True,
        )

    def _list_agent_profiles() -> list[tuple[str, str]]:
        if not state.profile_set:
            return []
        return [
            (profile.name, f"{profile.name} ({profile.provider}, {profile.model})")
            for profile in state.profile_set.profiles
        ]

    async def _on_agent_select(profile_name: str) -> str:
        changed = state.set_model_value(profile_name)
        return f"Model changed to: {changed}"

    def _recent_session_suggestions() -> list[ResumeSuggestion]:
        suggestions: list[ResumeSuggestion] = [
            ResumeSuggestion(
                value=state.session_id[:8],
                display=f"{state.session_id[:8]}  current session  {state.cwd}",
                meta="current",
            )
        ]
        for summary in list_session_summaries_sync(limit=20):
            label = summary.cwd or summary.id
            detail = f"{summary.message_count} msgs  {label}" if summary.message_count else label
            suggestions.append(
                ResumeSuggestion(
                    value=summary.prefix,
                    display=f"{summary.prefix}  {detail}",
                    meta="recent session",
                )
            )

        deduped: list[ResumeSuggestion] = []
        seen: set[str] = set()
        for suggestion in suggestions:
            if not suggestion.value or suggestion.value in seen:
                continue
            seen.add(suggestion.value)
            deduped.append(suggestion)
        return deduped[:20]

    tui = EnvAgentTui(
        session_id=state.session_id,
        get_status_meta=lambda: _status_meta(state),
        on_prompt=_on_prompt,
        on_command=_on_command,
        completer=build_completer(
            model_suggestions=lambda: (
                [profile.name for profile in state.profile_set.profiles]
                if state.profile_set
                else []
            ),
            resume_suggestions=_recent_session_suggestions,
            workspace_root=state.cwd,
            command_specs=get_command_info_list(state.cwd),
        ),
        startup_messages=_build_tui_startup_messages(state),
        list_agents=_list_agent_profiles,
        on_agent_select=_on_agent_select,
        command_specs=get_command_info_list(state.cwd),
        dev_mode=state.dev_mode,
    )
    permission_request = tui.prompt_permission
    input_draft_setter = tui.set_input_draft
    await tui.run()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--prompt", "prompt_text", default="", help="One-shot prompt to run and exit.")
@click.option(
    "--model", default="sonnet", show_default=True, help="Model alias or full model name."
)
@click.option("--cwd", default=".", show_default=True, help="Working directory.")
@click.option(
    "--permission-mode",
    type=click.Choice(["default", "plan", "acceptEdits", "bypassPermissions"], case_sensitive=True),
    default="default",
    show_default=True,
)
@click.option("--max-turns", default=200, show_default=True, type=int)
@click.option("--enable-thinking/--no-enable-thinking", default=False, show_default=True)
@click.option("--thinking-budget", default=None, type=int)
@click.option("--session", "session_id", default=None, help="Existing session id to resume.")
@click.option("--enable-mcp/--no-enable-mcp", default=False, show_default=True)
@click.option("--dev/--no-dev", default=False, show_default=True, help="Enable development mode.")
def main(
    prompt_text: str,
    model: str,
    cwd: str,
    permission_mode: str,
    max_turns: int,
    enable_thinking: bool,
    thinking_budget: int | None,
    session_id: str | None,
    enable_mcp: bool,
    dev: bool,
) -> None:
    """Run eagent CLI."""

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    abs_cwd = os.path.abspath(cwd)

    async def _runner() -> bool:
        state = await _build_state(
            api_key=api_key,
            model=model,
            cwd=abs_cwd,
            permission_mode=permission_mode,  # type: ignore[arg-type]
            enable_thinking=enable_thinking,
            thinking_budget=thinking_budget,
            max_turns=max_turns,
            enable_mcp=enable_mcp,
            dev_mode=dev,
            session_id=session_id,
        )

        if not state.api_key and os.environ.get("ENV_AGENT_MOCK", "").lower() not in {
            "1",
            "true",
            "yes",
        }:
            click.echo(
                "Warning: no active key found (agent.json or ANTHROPIC_API_KEY). "
                "Falling back to mock mode.",
                err=True,
            )

        try:
            if prompt_text:
                if prompt_text.startswith("/"):
                    should_exit = await _run_command(state, prompt_text)
                    if should_exit:
                        if state.reload_requested:
                            click.echo(
                                "Reload requested from one-shot mode; restart skipped. "
                                "Use interactive mode with --dev."
                            )
                            state.reload_requested = False
                        return False
                else:
                    await _run_agent_prompt(state, prompt_text)
            else:
                await _interactive_loop(state)
        finally:
            await _run_session_end_hooks(state)
            if enable_mcp:
                await shutdown_mcp_servers()

        if state.reload_requested:
            return True

        click.echo(summarize_cost(state.cost_tracker, state.model_config))
        return False

    reload_requested = asyncio.run(_runner())
    if reload_requested:
        click.echo("Reloading RTE-AI (--dev)...")
        os.execv(sys.executable, [sys.executable, *ReloadArgs.current()])


if __name__ == "__main__":
    main()
