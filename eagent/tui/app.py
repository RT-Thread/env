"""Prompt-toolkit full-screen TUI for eagent."""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from prompt_toolkit.application import Application
from prompt_toolkit.completion import Completer
from prompt_toolkit.data_structures import Point
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.containers import ConditionalContainer, Float, FloatContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.shortcuts import radiolist_dialog
from prompt_toolkit.widgets import TextArea

from eagent.core.types import PermissionDecision, PermissionRule
from eagent.permissions.engine import add_session_rule
from eagent.tui.agent_picker import AgentPicker
from eagent.tui.status_bar import SPINNER_FRAMES, StatusBarRenderer, StatusBarState, StatusMeta
from eagent.tui.styles import TUI_STYLE
from eagent.utils.completer import extract_mention_query


@dataclass
class TuiState:
    status: str = "idle"
    status_text: str = "Ready"
    spinner_index: int = 0
    busy: bool = False
    input_mode: str = "compose"

    def on_submit(self) -> None:
        self.status = "running"
        self.status_text = "思考中..."
        self.busy = True

    def on_tool_start(self) -> None:
        self.status_text = "调用工具..."

    def on_compact(self) -> None:
        self.status_text = "整理上下文..."

    def on_assistant_text(self) -> None:
        if self.status == "running":
            self.status_text = "输出中..."

    def on_error(self) -> None:
        self.status = "error"
        self.status_text = "出现错误"
        self.busy = False

    def on_turn_complete(self) -> None:
        self.status = "idle"
        self.status_text = "Ready"
        self.busy = False

    def on_history_view(self) -> None:
        self.input_mode = "history_view"

    def on_edit_mode(self) -> None:
        self.input_mode = "compose"

    def on_agent_picker_mode(self) -> None:
        self.input_mode = "agent_picker"


@dataclass
class ToolPanel:
    seq: int
    tool_use_id: str
    tool_name: str
    input_preview: str
    started_at: float
    status: str = "running"
    is_error: bool = False
    duration_ms: int | None = None
    result_preview: str = ""
    result_detail: str = ""
    expanded: bool = False


@dataclass
class ActivityItem:
    seq: int
    text: str
    status: str = "running"
    started_at: float = field(default_factory=time.monotonic)
    ended_at: float | None = None


@dataclass
class TranscriptChunk:
    style: str
    text: str


class EnvAgentTui:
    def __init__(
        self,
        session_id: str,
        get_status_meta: Callable[[], StatusMeta],
        on_prompt: Callable[
            [str, Callable[[str], None], Callable[[dict[str, Any]], None]], Awaitable[None]
        ],
        on_command: Callable[
            [str, Callable[[str], None], Callable[[dict[str, Any]], None]], Awaitable[bool]
        ],
        completer: Completer | None = None,
        startup_messages: list[str] | None = None,
        list_agents: Callable[[], list[tuple[str, str]]] | None = None,
        on_agent_select: Callable[[str], Awaitable[str]] | None = None,
        command_specs: list[dict[str, Any]] | None = None,
        dev_mode: bool = False,
    ) -> None:
        self._session_id = session_id
        self._get_status_meta = get_status_meta
        self._on_prompt = on_prompt
        self._on_command = on_command
        self._startup_messages = startup_messages or []
        self._list_agents = list_agents
        self._on_agent_select = on_agent_select
        self._dev_mode = dev_mode
        self._command_specs = {
            str(spec.get("name", "")): spec for spec in (command_specs or []) if spec.get("name")
        }
        self._command_alias_to_name = self._build_command_alias_map(command_specs or [])
        self.state = TuiState()
        self._running = True
        self._assistant_block_open = False
        self._input_history: list[str] = []
        self._history_index: int | None = None
        self._default_hint = (
            "Enter 发送 | Alt+Enter 换行 | Esc/Ctrl+C 中断 | "
            "Tab 补全 | F2/F3/F4 工具面板 | F6 活动轨模式"
        )
        if self._dev_mode:
            self._default_hint += " | Ctrl-R 重载"
        self._idle_short_hint = "Enter 发送 | /help"
        if self._dev_mode:
            self._idle_short_hint += " | Ctrl-R 重载"
        self._hint_text = self._default_hint
        self._tool_panels: list[ToolPanel] = []
        self._tool_panel_index_by_id: dict[str, int] = {}
        self._selected_tool_panel: int = 0
        self._activities: list[ActivityItem] = []
        self._tool_activity_seq: dict[str, int] = {}
        self._activity_seq: int = 0
        self._animation_tick: int = 0
        self._turn_started_at: float | None = None
        self._model_wait_seq: int | None = None
        self._stream_seq: int | None = None
        self._assistant_started_in_turn: bool = False
        self._assistant_streaming_cursor: bool = False
        self._assistant_chunk_index: int | None = None
        self._activity_compact_mode: bool = True
        self._active_turn_task: asyncio.Task[None] | None = None
        self._queued_inputs: list[str] = []
        self._status_tool_text: str | None = None
        self._status_tool_running: bool = False
        self._status_tool_error: bool = False
        self._agent_picker = AgentPicker()
        self._transcript_chunks: list[TranscriptChunk] = []
        self._transcript_cursor_line: int = 0
        self._transcript_cursor_col: int = 0
        self._suspend_mention_autocomplete_once: bool = False
        self._status_bar_renderer = StatusBarRenderer()

        self.transcript = Window(
            content=FormattedTextControl(
                self._transcript_fragments,
                get_cursor_position=self._transcript_cursor_position,
                show_cursor=False,
            ),
            style="class:transcript",
            wrap_lines=True,
            right_margins=[ScrollbarMargin(display_arrows=False)],
        )
        history_read_only = Condition(
            lambda: self.state.input_mode in {"history_view", "agent_picker"}
        )
        self.input = TextArea(
            height=self._input_height_dimension,
            prompt="> ",
            style="class:input",
            multiline=True,
            wrap_lines=True,
            completer=completer,
            complete_while_typing=True,
            read_only=history_read_only,
        )
        self.input.buffer.on_text_changed += self._on_input_text_changed

        self.status_bar = Window(
            content=FormattedTextControl(self._status_fragments),
            height=D.exact(1),
            style="class:status",
        )
        self.activity_rail = Window(
            content=FormattedTextControl(self._activity_fragments),
            height=D(min=1, max=4),
            style="class:activity",
        )
        self._activity_rail_visible = Condition(
            lambda: self.state.busy or self._running_activity_count() > 0
        )
        self.activity_rail_container = ConditionalContainer(
            content=self.activity_rail,
            filter=self._activity_rail_visible,
        )
        self.tool_panel = Window(
            content=FormattedTextControl(self._tool_panel_fragments),
            height=D(min=1, max=8),
            style="class:toolpanel",
        )
        self._tool_panel_visible = Condition(lambda: bool(self._tool_panels))
        self.tool_panel_container = ConditionalContainer(
            content=self.tool_panel,
            filter=self._tool_panel_visible,
        )
        self._hint_visible = Condition(lambda: self.app.output.get_size().columns >= 72)
        self.hint_bar = Window(
            content=FormattedTextControl(self._hint_fragments),
            height=D.exact(1),
            style="class:hint",
        )
        self.hint_bar_container = ConditionalContainer(
            content=self.hint_bar,
            filter=self._hint_visible,
        )
        self.agent_picker_panel = Window(
            content=FormattedTextControl(self._agent_picker_fragments),
            height=D(min=3, max=8),
            style="class:toolpanel",
        )
        self._agent_picker_visible = Condition(lambda: self._agent_picker.active)
        self.agent_picker_container = ConditionalContainer(
            content=self.agent_picker_panel,
            filter=self._agent_picker_visible,
        )

        body = HSplit(
            [
                self.transcript,
                self.tool_panel_container,
                self.activity_rail_container,
                self.agent_picker_container,
                self.input,
                self.status_bar,
                self.hint_bar_container,
            ]
        )
        root_container = FloatContainer(
            content=body,
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    width=lambda: max(40, self.app.output.get_size().columns - 4),
                    content=CompletionsMenu(max_height=8, scroll_offset=1),
                )
            ],
        )
        kb = KeyBindings()
        focus_input = has_focus(self.input)

        @kb.add("c-d")
        def _exit(_event) -> None:
            self._running = False
            self.app.exit()

        @kb.add("c-c")
        def _ctrl_c(event) -> None:
            self._handle_ctrl_c()
            event.app.invalidate()

        @kb.add("c-r", filter=focus_input & Condition(lambda: self._dev_mode))
        def _reload(event) -> None:
            if self._trigger_dev_reload():
                event.app.invalidate()

        @kb.add("enter", filter=focus_input)
        def _enter(event) -> None:
            if self._agent_picker.active:
                self._confirm_agent_picker()
                event.app.invalidate()
                return
            if self._accept_completion_selection():
                event.app.invalidate()
                return
            self._accept_input(self.input.buffer)
            event.app.invalidate()

        @kb.add("escape", "enter", filter=focus_input)
        def _alt_enter(event) -> None:
            self._insert_newline(event)

        @kb.add("escape", filter=Condition(lambda: self.state.busy))
        def _interrupt(event) -> None:
            self._interrupt_active_turn()
            event.app.invalidate()

        @kb.add("escape", filter=Condition(lambda: self._agent_picker.active))
        def _cancel_picker(event) -> None:
            self._cancel_agent_picker()
            event.app.invalidate()

        @kb.add("up", filter=focus_input)
        def _up(event) -> None:
            if self._agent_picker.active:
                self._move_agent_picker(step=-1)
                event.app.invalidate()
                return
            if self._move_completion_selection(step=-1):
                event.app.invalidate()
                return
            self._browse_history(step=-1)
            event.app.invalidate()

        @kb.add("down", filter=focus_input)
        def _down(event) -> None:
            if self._agent_picker.active:
                self._move_agent_picker(step=1)
                event.app.invalidate()
                return
            if self._move_completion_selection(step=1):
                event.app.invalidate()
                return
            self._browse_history(step=1)
            event.app.invalidate()

        @kb.add(
            "left",
            filter=focus_input & Condition(lambda: self.state.input_mode == "history_view"),
        )
        def _left(event) -> None:
            self._enter_edit_mode_from_history(direction="left")
            event.app.invalidate()

        @kb.add(
            "right",
            filter=focus_input & Condition(lambda: self.state.input_mode == "history_view"),
        )
        def _right(event) -> None:
            self._enter_edit_mode_from_history(direction="right")
            event.app.invalidate()

        @kb.add("f2")
        def _toggle_tool(event) -> None:
            self._toggle_selected_tool_panel()
            event.app.invalidate()

        @kb.add("f3")
        def _prev_tool(event) -> None:
            self._move_tool_panel_selection(step=-1)
            event.app.invalidate()

        @kb.add("f4")
        def _next_tool(event) -> None:
            self._move_tool_panel_selection(step=1)
            event.app.invalidate()

        @kb.add("f6")
        def _toggle_activity_mode(event) -> None:
            self._activity_compact_mode = not self._activity_compact_mode
            event.app.invalidate()

        @kb.add("tab")
        def _tab(event) -> None:
            buffer = self.input.buffer
            if buffer.complete_state:
                buffer.complete_next()
            else:
                buffer.start_completion(select_first=True)
            event.app.invalidate()

        @kb.add("s-tab")
        def _shift_tab(event) -> None:
            buffer = self.input.buffer
            if buffer.complete_state:
                buffer.complete_previous()
            else:
                buffer.start_completion(select_first=False)
            event.app.invalidate()

        self.app = Application(
            layout=Layout(root_container, focused_element=self.input),
            key_bindings=kb,
            full_screen=False,
            style=TUI_STYLE,
        )
        self._refresh_hint()

    @staticmethod
    def _build_command_alias_map(command_specs: list[dict[str, Any]]) -> dict[str, str]:
        alias_map: dict[str, str] = {}
        for spec in command_specs:
            name = str(spec.get("name", "")).strip()
            if not name:
                continue
            aliases_raw = spec.get("aliases", [])
            if not isinstance(aliases_raw, list):
                continue
            for alias in aliases_raw:
                alias_text = str(alias).strip()
                if not alias_text:
                    continue
                alias_map[alias_text] = name
        return alias_map

    async def run(self) -> None:
        for message in self._startup_messages:
            self._append_line(f"Warning: {message}")
        spinner_task = self.app.create_background_task(self._spin())
        try:
            await self.app.run_async()
        finally:
            spinner_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await spinner_task

    async def prompt_permission(
        self, tool: str, input_data: Any, message: str
    ) -> PermissionDecision:
        pending = self._start_activity(f"权限请求: {tool}")
        preview = str(input_data)[:300]
        selected = await radiolist_dialog(
            title=f"Permission Required: {tool}",
            text=f"{message}\n\nInput preview:\n{preview}\n\nChoose action:",
            values=[
                ("allow_once", "Allow once"),
                ("allow_session", "Always allow this tool in current session"),
                ("deny_once", "Deny once"),
                ("deny_session", "Always deny this tool in current session"),
            ],
        ).run_async()

        if selected == "allow_once":
            self._finish_activity(pending.seq, status="done", suffix=" 已允许")
            self._append_line(f"Permission: allow {tool}")
            self.app.invalidate()
            return PermissionDecision(behavior="allow")

        if selected == "allow_session":
            add_session_rule(PermissionRule(tool=tool, behavior="allow", source="session"))
            self._finish_activity(pending.seq, status="done", suffix=" 已允许（会话记忆）")
            self._append_line(f"Permission: allow {tool} (session)")
            self.app.invalidate()
            return PermissionDecision(behavior="allow")

        if selected == "deny_session":
            add_session_rule(PermissionRule(tool=tool, behavior="deny", source="session"))
            self._finish_activity(pending.seq, status="error", suffix=" 已拒绝（会话记忆）")
            self._append_line(f"Permission: deny {tool} (session)")
            self.app.invalidate()
            return PermissionDecision(behavior="deny", message=f"Denied by user for {tool}")

        self._finish_activity(pending.seq, status="error", suffix=" 已拒绝")
        self._append_line(f"Permission: deny {tool}")
        self.app.invalidate()
        return PermissionDecision(behavior="deny", message=f"Denied by user for {tool}")

    def _start_activity(self, text: str) -> ActivityItem:
        self._activity_seq += 1
        item = ActivityItem(seq=self._activity_seq, text=text)
        self._activities.append(item)
        if len(self._activities) > 24:
            self._activities = self._activities[-24:]
        return item

    def _finish_activity(self, seq: int | None, status: str = "done", suffix: str = "") -> None:
        if seq is None:
            return
        item = next((activity for activity in self._activities if activity.seq == seq), None)
        if item is None or item.status != "running":
            return
        item.status = status
        item.ended_at = time.monotonic()
        if suffix:
            item.text = f"{item.text}{suffix}"

    def _finish_running_activities(self, status: str = "done") -> None:
        for item in self._activities:
            if item.status == "running":
                item.status = status
                item.ended_at = time.monotonic()

    def _reset_turn_feedback(self) -> None:
        self._activities = []
        self._tool_activity_seq = {}
        self._activity_seq = 0
        self._turn_started_at = time.monotonic()
        self._model_wait_seq = None
        self._stream_seq = None
        self._assistant_started_in_turn = False
        self._assistant_streaming_cursor = False
        self._assistant_block_open = False
        self._assistant_chunk_index = None
        self._status_tool_text = None
        self._status_tool_running = False
        self._status_tool_error = False

    def _mark_turn_complete(self, failed: bool = False, message: str | None = None) -> None:
        self._finish_activity(self._model_wait_seq, status="done")
        self._finish_activity(self._stream_seq, status="done")
        self._finish_running_activities(status="error" if failed else "done")
        if self._turn_started_at is None:
            return
        elapsed = time.monotonic() - self._turn_started_at
        if message:
            item = self._start_activity(message)
            item.status = "error" if failed else "done"
            item.ended_at = time.monotonic()
            return
        if failed:
            item = self._start_activity(f"回合结束（错误） {elapsed:.1f}s")
            item.status = "error"
            item.ended_at = time.monotonic()
            return
        finished = self._start_activity(f"回合完成 {elapsed:.1f}s")
        finished.status = "done"
        finished.ended_at = time.monotonic()

    def _running_activity_count(self) -> int:
        return sum(1 for activity in self._activities if activity.status == "running")

    def _handle_ctrl_c(self) -> None:
        if self.state.busy:
            self._interrupt_active_turn(source="Ctrl+C")
            return
        self._running = False
        self.app.exit()

    def _interrupt_active_turn(self, source: str = "Esc") -> None:
        if not self.state.busy:
            return
        task = self._active_turn_task
        if task is None or task.done():
            return
        self._append_line(f"System: Interrupt requested ({source})")
        self._start_activity(f"用户中断当前回合 ({source})")
        task.cancel()

    def _shimmer_segments(
        self, text: str, base_style: str, shine_style: str, width: int = 7
    ) -> list[tuple[str, str]]:
        if not text:
            return []
        cycle = len(text) + width
        head = self._animation_tick % cycle
        start = head - width
        fragments: list[tuple[str, str]] = []
        for idx, char in enumerate(text):
            style = shine_style if start <= idx <= head else base_style
            if fragments and fragments[-1][0] == style:
                prev_style, prev_text = fragments[-1]
                fragments[-1] = (prev_style, prev_text + char)
            else:
                fragments.append((style, char))
        return fragments

    def _activity_fragments(self) -> FormattedText:
        fragments: list[tuple[str, str]] = []

        # AI 流式输出动态指示器（左侧）
        if self._assistant_streaming_cursor and self._assistant_started_in_turn:
            spinner_char = SPINNER_FRAMES[self.state.spinner_index]
            fragments.append(("class:activity.ai_streaming", f" {spinner_char} AI 正在输出 "))

        if not self._activities:
            label = " Activity[min]: idle" if self._activity_compact_mode else " Activity: idle"
            fragments.append(("class:activity.empty", label))
            return FormattedText(fragments)

        lines = self._activities[-1:] if self._activity_compact_mode else self._activities[-4:]
        if self._activity_compact_mode:
            fragments.append(("class:activity.empty", " | "))
        for item in lines:
            if item.status == "running":
                prefix = " … "
                fragments.append(("class:activity.running", prefix))
                shimmer = self._shimmer_segments(
                    item.text,
                    base_style="class:activity.running",
                    shine_style="class:activity.shine",
                )
                fragments.extend(shimmer)
                fragments.append(("class:activity.running", "\n"))
                continue

            prefix = " ✓ " if item.status == "done" else " ! "
            style = "class:activity.done" if item.status == "done" else "class:activity.error"
            text = item.text
            if item.ended_at is not None:
                duration = int((item.ended_at - item.started_at) * 1000)
                text = f"{text} ({duration}ms)"
            fragments.append((style, f"{prefix}{text}\n"))

        if self._activity_compact_mode and len(fragments) > 1:
            # Keep compact mode to a single visible row.
            text = "".join(chunk for _style, chunk in fragments).rstrip("\n")
            return FormattedText([("class:activity.running", text)])

        return FormattedText(fragments)

    def _status_fragments(self) -> FormattedText:
        return self._status_bar_renderer.render(
            StatusBarState(
                columns=self.app.output.get_size().columns,
                busy=self.state.busy,
                status=self.state.status,
                status_text=self.state.status_text,
                input_mode=self.state.input_mode,
                spinner_index=self.state.spinner_index,
                running_activity_count=self._running_activity_count(),
                tool_text=self._status_tool_text,
                tool_running=self._status_tool_running,
                tool_error=self._status_tool_error,
                activity_compact_mode=self._activity_compact_mode,
                queued_input_count=len(self._queued_inputs),
                meta=self._get_status_meta(),
            )
        )

    def _tool_panel_fragments(self) -> FormattedText:
        if not self._tool_panels:
            return FormattedText(
                [("class:toolpanel.empty", " Tool Panels: no tool calls in current turn")]
            )

        has_expanded = any(panel.expanded for panel in self._tool_panels)
        if has_expanded:
            panels = self._tool_panels
        else:
            selected = self._tool_panels[self._selected_tool_panel]
            panels = [selected]
        hidden_count = len(self._tool_panels) - len(panels)

        fragments: list[tuple[str, str]] = []
        for panel in panels:
            idx = self._tool_panel_index_by_id.get(panel.tool_use_id, 0)
            marker = ">" if idx == self._selected_tool_panel else " "
            arrow = "▼" if panel.expanded else "▶"
            status = panel.status
            if panel.status == "done":
                status = "error" if panel.is_error else "ok"
            duration = f" {panel.duration_ms}ms" if panel.duration_ms is not None else ""
            more = f" (+{hidden_count} more)" if hidden_count > 0 and not has_expanded else ""
            summary = (
                f" {marker} {arrow} #{panel.seq} {panel.tool_name} "
                f"{status}{duration} | {panel.input_preview}{more}\n"
            )
            summary_class = "class:toolpanel.error" if panel.is_error else "class:toolpanel.summary"
            fragments.append((summary_class, summary))

            if panel.expanded:
                detail = panel.result_detail or panel.result_preview or "(no output)"
                fragments.append(("class:toolpanel.detail", f"    {detail}\n"))

        return FormattedText(fragments)

    def _hint_fragments(self) -> FormattedText:
        return FormattedText([("class:hint.text", f" {self._hint_text}")])

    def _agent_picker_fragments(self) -> FormattedText:
        return self._agent_picker.render()

    def _transcript_fragments(self) -> FormattedText:
        if not self._transcript_chunks:
            return FormattedText([])
        fragments: list[tuple[str, str]] = [
            (chunk.style, chunk.text) for chunk in self._transcript_chunks
        ]
        if self._should_show_idle_ai_prompt():
            if fragments and not fragments[-1][1].endswith("\n"):
                fragments.append(("class:transcript.system", "\n"))
            idle_icon = ">" if (self._animation_tick // 4) % 2 == 0 else " "
            fragments.append(("class:transcript.ai_idle_prompt", f"{idle_icon} \n"))
        return FormattedText(fragments)

    def _should_show_idle_ai_prompt(self) -> bool:
        return (
            self.state.status == "idle"
            and not self.state.busy
            and not self._assistant_block_open
            and not self._assistant_streaming_cursor
            and not self._status_tool_running
            and self._running_activity_count() == 0
        )

    def _transcript_cursor_position(self) -> Point:
        return Point(x=self._transcript_cursor_col, y=self._transcript_cursor_line)

    def _advance_transcript_cursor(self, text: str) -> None:
        if not text:
            return
        line_breaks = text.count("\n")
        if line_breaks == 0:
            self._transcript_cursor_col += len(text)
            return
        self._transcript_cursor_line += line_breaks
        self._transcript_cursor_col = len(text.rsplit("\n", 1)[-1])

    def _append_transcript_text(self, text: str, style: str) -> None:
        if not text:
            return
        if self._transcript_chunks and self._transcript_chunks[-1].style == style:
            self._transcript_chunks[-1].text += text
        else:
            self._transcript_chunks.append(TranscriptChunk(style=style, text=text))
        self._advance_transcript_cursor(text)

    def _transcript_last_char(self) -> str | None:
        for chunk in reversed(self._transcript_chunks):
            if chunk.text:
                return chunk.text[-1]
        return None

    def _input_visible_lines(self) -> int:
        if not hasattr(self, "input"):
            return 1
        text = self.input.buffer.text
        if not text:
            return 1
        return text.count("\n") + 1

    def _input_max_rows(self) -> int:
        rows = 24
        if hasattr(self, "app"):
            with contextlib.suppress(Exception):
                rows = int(self.app.output.get_size().rows)
        return max(4, rows // 3)

    def _input_height_dimension(self) -> D:
        max_rows = self._input_max_rows()
        preferred = min(max_rows, max(1, self._input_visible_lines()))
        # Keep input height tied to content lines; don't consume extra free space.
        return D(min=1, preferred=preferred, max=max_rows, weight=0)

    async def _spin(self) -> None:
        while self._running:
            if (
                self.state.busy
                or self._running_activity_count() > 0
                or self._should_show_idle_ai_prompt()
            ):
                self.state.spinner_index = (self.state.spinner_index + 1) % len(SPINNER_FRAMES)
                self._animation_tick = (self._animation_tick + 1) % 100_000
                self.app.invalidate()
            await asyncio.sleep(0.12)

    def _accept_input(self, buffer) -> None:
        raw = buffer.text
        if not raw.strip():
            return

        text = raw.rstrip("\n")
        if self.state.busy:
            self._record_history(text)
            self._history_index = None
            self.state.on_edit_mode()
            buffer.text = ""
            self._queued_inputs.append(text)
            queued = self._start_activity(
                f"已排队后续输入（第 {len(self._queued_inputs)} 条）"
            )
            queued.status = "done"
            queued.ended_at = time.monotonic()
            self._append_line(
                f"System: queued follow-up ({len(self._queued_inputs)} pending)"
            )
            self._refresh_hint()
            self.app.invalidate()
            return

        self._record_history(text)
        self._history_index = None
        self.state.on_edit_mode()
        buffer.text = ""
        self._refresh_hint()
        self._active_turn_task = self.app.create_background_task(self._handle_submit(text))

    def _record_history(self, text: str) -> None:
        if not text.strip():
            return
        if self._input_history and self._input_history[-1] == text:
            return
        self._input_history.append(text)

    def _set_input_text(self, text: str) -> None:
        self.input.buffer.set_document(
            Document(text=text, cursor_position=len(text)),
            bypass_readonly=True,
        )
        self._refresh_hint()

    def set_input_draft(self, text: str) -> None:
        self.state.on_edit_mode()
        self._set_input_text(text)
        self.app.invalidate()

    def _browse_history(self, step: int) -> None:
        if self.state.busy or not self._input_history:
            return

        if self._history_index is None:
            if step > 0:
                return
            self._history_index = len(self._input_history) - 1
        else:
            next_index = self._history_index + step
            if next_index < 0:
                next_index = 0
            if next_index >= len(self._input_history):
                self._history_index = None
                self.state.on_edit_mode()
                self._set_input_text("")
                self.app.invalidate()
                return
            self._history_index = next_index

        self.state.on_history_view()
        self._set_input_text(self._input_history[self._history_index])
        self.app.invalidate()

    def _enter_edit_mode_from_history(self, direction: str) -> None:
        if self.state.input_mode != "history_view":
            return
        self.state.on_edit_mode()
        if direction == "left":
            self.input.buffer.cursor_left(count=1)
        else:
            self.input.buffer.cursor_right(count=1)
        self._refresh_hint()
        self.app.invalidate()

    def _insert_newline(self, event) -> None:
        if self.state.input_mode == "history_view":
            self.state.on_edit_mode()
        event.current_buffer.insert_text("\n")
        self._refresh_hint()

    def _trigger_dev_reload(self) -> bool:
        if not self._dev_mode or self._agent_picker.active:
            return False
        if self.state.input_mode == "history_view":
            self.state.on_edit_mode()
        self._set_input_text("/reload")
        self._accept_input(self.input.buffer)
        return True

    def _move_completion_selection(self, step: int) -> bool:
        buffer = self.input.buffer
        state = buffer.complete_state
        if state is None or not state.completions:
            return False
        if step < 0:
            buffer.complete_previous(count=abs(step))
        elif step > 0:
            buffer.complete_next(count=step)
        return True

    def _accept_completion_selection(self) -> bool:
        buffer = self.input.buffer
        state = buffer.complete_state
        if state is None or not state.completions:
            return False
        completion = state.current_completion or state.completions[0]
        self._suspend_mention_autocomplete_once = True
        buffer.apply_completion(completion)
        self.state.on_edit_mode()
        self._history_index = None
        self._refresh_hint()
        return True

    def _toggle_selected_tool_panel(self) -> None:
        if not self._tool_panels:
            return
        panel = self._tool_panels[self._selected_tool_panel]
        panel.expanded = not panel.expanded

    def _move_tool_panel_selection(self, step: int) -> None:
        if not self._tool_panels:
            return
        count = len(self._tool_panels)
        self._selected_tool_panel = (self._selected_tool_panel + step) % count

    def _move_agent_picker(self, step: int) -> None:
        self._agent_picker.move(step)

    def _confirm_agent_picker(self) -> None:
        self._agent_picker.confirm()

    def _cancel_agent_picker(self) -> None:
        self._agent_picker.cancel()

    def _format_command_hint(self, name: str, spec: dict[str, Any]) -> str:
        arg_hint = str(spec.get("argument_hint", "")).strip()
        description = str(spec.get("description", "")).strip()
        examples_raw = spec.get("examples", [])
        examples = [str(item).strip() for item in examples_raw if str(item).strip()]

        head = f"/{name}"
        if arg_hint:
            head = f"{head} {arg_hint}"
        if description:
            head = f"{head} - {description}"
        if examples:
            head = f"{head} | e.g. {examples[0]}"
        return head

    def _on_input_text_changed(self, _event: object) -> None:
        self._refresh_hint()
        if self._suspend_mention_autocomplete_once:
            self._suspend_mention_autocomplete_once = False
            return
        self._maybe_autocomplete_mentions()

    def _maybe_autocomplete_mentions(self) -> None:
        if self.state.input_mode != "compose":
            return

        buffer = self.input.buffer
        if buffer.completer is None or buffer.complete_state is not None:
            return

        query = extract_mention_query(buffer.document.text_before_cursor)
        if query is None:
            return

        buffer.start_completion(select_first=False)

    def _refresh_hint(self) -> None:
        text = self.input.buffer.text
        default_hint = self._default_hint
        if self.state.input_mode == "agent_picker":
            default_hint = "选择 Agent：Up/Down 移动，Enter 确认，Esc 取消"
        elif self.state.input_mode == "history_view":
            default_hint = "历史浏览：Up/Down 浏览，Left/Right 进入编辑"
        elif self.state.busy:
            runtime_note = self._current_runtime_hint()
            default_hint = f"运行中：{runtime_note} | Esc/Ctrl+C 中断当前回合 | Alt+Enter 换行"
        elif not text:
            default_hint = self._idle_short_hint

        if not text.startswith("/"):
            self._hint_text = default_hint
            return

        first_line = text.splitlines()[0]
        raw = first_line[1:]
        if not raw:
            self._hint_text = "输入命令并按 Tab 补全，例如 /model 或 /agent"
            return

        parts = raw.split(maxsplit=1)
        command_token = parts[0].strip()
        canonical_token = self._command_alias_to_name.get(command_token, command_token)
        has_args = len(parts) > 1 or first_line.endswith(" ")

        if not has_args:
            matches = [
                name for name in self._command_specs if name.startswith(canonical_token)
            ]
            alias_matches = [
                alias
                for alias in self._command_alias_to_name
                if alias.startswith(command_token)
            ]
            if len(matches) == 1 and not alias_matches:
                command_name = matches[0]
                self._hint_text = self._format_command_hint(
                    command_name, self._command_specs[command_name]
                )
                return
            if len(matches) == 1 and alias_matches:
                command_name = matches[0]
                self._hint_text = self._format_command_hint(
                    command_name, self._command_specs[command_name]
                )
                return
            if matches or alias_matches:
                merged = {f"/{name}" for name in matches}
                merged.update(f"/{alias}" for alias in alias_matches)
                joined = ", ".join(sorted(merged)[:6])
                self._hint_text = f"命令候选：{joined}"
                return
            self._hint_text = "未知命令，输入 /help 查看命令列表"
            return

        spec = self._command_specs.get(canonical_token)
        if spec is None:
            self._hint_text = "未知命令，输入 /help 查看命令列表"
            return
        self._hint_text = self._format_command_hint(canonical_token, spec)

    def _current_runtime_hint(self) -> str:
        if self._tool_panels:
            panel = self._tool_panels[self._selected_tool_panel]
            if panel.status == "running":
                return f"工具 {panel.tool_name} 运行中"
            if panel.is_error:
                return f"工具 {panel.tool_name} 失败"
            return f"工具 {panel.tool_name} 完成"

        running_activity = next(
            (item for item in reversed(self._activities) if item.status == "running"),
            None,
        )
        if running_activity is not None:
            return running_activity.text
        if self._activities:
            return self._activities[-1].text
        return "处理中"

    def _format_tool_input_preview(self, input_data: Any) -> str:
        if isinstance(input_data, dict):
            command = input_data.get("command")
            if isinstance(command, str) and command.strip():
                return command.strip()[:80]
            file_path = (
                input_data.get("file_path")
                or input_data.get("path")
                or input_data.get("filePath")
                or input_data.get("filename")
            )
            if isinstance(file_path, str) and file_path.strip():
                return file_path.strip()[:80]
        return str(input_data)[:80]

    def _shorten_result(self, text: str, limit: int = 300) -> str:
        cleaned = text.strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[:limit] + " ..."

    def _register_tool_start(self, event: dict[str, Any]) -> ToolPanel:
        tool_use_id = str(event.get("tool_use_id") or f"tool-{len(self._tool_panels)+1}")
        panel = ToolPanel(
            seq=len(self._tool_panels) + 1,
            tool_use_id=tool_use_id,
            tool_name=str(event.get("tool_name") or "Tool"),
            input_preview=self._format_tool_input_preview(event.get("input", {})),
            started_at=time.monotonic(),
            expanded=False,
        )
        self._tool_panel_index_by_id[tool_use_id] = len(self._tool_panels)
        self._tool_panels.append(panel)
        self._selected_tool_panel = len(self._tool_panels) - 1
        return panel

    def _register_tool_result(self, event: dict[str, Any]) -> ToolPanel:
        tool_use_id = str(event.get("tool_use_id") or "")
        panel_index = self._tool_panel_index_by_id.get(tool_use_id)
        if panel_index is None:
            panel = self._register_tool_start(
                {
                    "tool_use_id": tool_use_id or f"tool-{len(self._tool_panels)+1}",
                    "tool_name": str(event.get("tool_name") or "Tool"),
                    "input": {},
                }
            )
            panel_index = self._tool_panel_index_by_id[panel.tool_use_id]
        panel = self._tool_panels[panel_index]

        panel.status = "done"
        panel.is_error = bool(event.get("is_error", False))
        panel.duration_ms = int((time.monotonic() - panel.started_at) * 1000)
        raw_result = str(event.get("result") or "")
        panel.result_preview = self._shorten_result(raw_result, limit=120)
        panel.result_detail = self._shorten_result(raw_result, limit=1200)
        if panel.is_error:
            panel.expanded = True
        return panel

    async def _handle_submit(self, text: str) -> None:
        current_text = text
        try:
            while True:
                if current_text.strip() == "/agent":
                    await self._handle_agent_picker()
                else:
                    self._close_assistant_block()
                    self._reset_turn_feedback()
                    self._tool_panels = []
                    self._tool_panel_index_by_id = {}
                    self._selected_tool_panel = 0
                    self.state.on_submit()
                    self._append_user_block(current_text)
                    self._start_activity("准备上下文")
                    self._refresh_hint()
                    self.app.invalidate()

                    self._finish_running_activities(status="done")
                    if current_text.startswith("/"):
                        command_activity = self._start_activity("执行命令")
                        should_exit = await self._on_command(
                            current_text, self._append_line, self._on_event
                        )
                        self._finish_activity(command_activity.seq, status="done")
                        if should_exit:
                            self._running = False
                            self.app.exit()
                            break
                    else:
                        self._model_wait_seq = self._start_activity("请求模型，等待首个响应").seq
                        await self._on_prompt(current_text, self._append_assistant, self._on_event)
                    self._close_assistant_block()
                    self.state.on_turn_complete()
                    self._mark_turn_complete()
                    self._refresh_hint()
                    self.app.invalidate()

                if not self._queued_inputs:
                    break

                queued_remaining = max(0, len(self._queued_inputs) - 1)
                current_text = self._queued_inputs.pop(0)
                self._append_line(
                    f"System: running queued follow-up ({queued_remaining} left after this)"
                )
                self._refresh_hint()
                self.app.invalidate()
        except asyncio.CancelledError:
            self._close_assistant_block(finalize=False)
            self.state.on_turn_complete()
            self._mark_turn_complete(failed=False, message="回合已中断")
            if self._queued_inputs:
                self._append_line("System: queued follow-ups cleared by interrupt")
                self._queued_inputs.clear()
            self._refresh_hint()
            self.app.invalidate()
        except Exception as exc:
            self._close_assistant_block(finalize=False)
            self._append_line(f"Error: {exc}")
            self.state.on_error()
            self._mark_turn_complete(failed=True)
            if self._queued_inputs:
                self._append_line("System: queued follow-ups cleared after error")
                self._queued_inputs.clear()
            self._refresh_hint()
            self.app.invalidate()
        finally:
            self._active_turn_task = None

    async def _handle_agent_picker(self) -> None:
        if self._list_agents is None or self._on_agent_select is None:
            self._append_line("Error: /agent is not available in this mode.")
            self.app.invalidate()
            return

        profiles = self._list_agents()
        if not profiles:
            self._append_line("No agent profiles found in ~/.env/agent.json.")
            self.app.invalidate()
            return

        loop = asyncio.get_running_loop()
        self._agent_picker.open(profiles, loop)
        self.state.on_agent_picker_mode()
        self._set_input_text("")
        self._refresh_hint()
        self.app.invalidate()

        selected = await self._agent_picker.wait()

        try:
            if selected is None:
                self._append_line("Agent selection cancelled.")
                return
            message = await self._on_agent_select(str(selected))
            self._append_line(message)
        except Exception as exc:
            self._append_line(f"Error: {exc}")
        finally:
            self._agent_picker.close()
            self.state.on_edit_mode()
            self._refresh_hint()
            self.app.invalidate()

    def _on_event(self, event: dict[str, Any]) -> None:
        event_type = str(event.get("type"))
        if event_type == "tool_start":
            self._close_assistant_block(finalize=False)
            self.state.on_tool_start()
            panel = self._register_tool_start(event)
            activity = self._start_activity(f"调用工具 {panel.tool_name}")
            self._tool_activity_seq[panel.tool_use_id] = activity.seq
            self._status_tool_text = f"Tool#{panel.seq} {panel.tool_name} running"
            self._status_tool_running = True
            self._status_tool_error = False
        elif event_type == "tool_result":
            self._close_assistant_block(finalize=False)
            panel = self._register_tool_result(event)
            status = "failed" if panel.is_error else "done"
            seq = self._tool_activity_seq.get(panel.tool_use_id)
            self._finish_activity(
                seq,
                status="error" if panel.is_error else "done",
                suffix=f" {status}",
            )
            self._status_tool_text = f"Tool#{panel.seq} {panel.tool_name} {status}"
            self._status_tool_running = False
            self._status_tool_error = panel.is_error
        elif event_type == "compact":
            self._close_assistant_block(finalize=False)
            self.state.on_compact()
            compact_activity = self._start_activity("系统压缩上下文")
            compact_activity.status = "done"
            compact_activity.ended_at = time.monotonic()
            self._append_line("System: Context compacted")
        elif event_type == "error":
            self._close_assistant_block(finalize=False)
            self.state.on_error()
            error_activity = self._start_activity(f"模型错误: {event.get('error')}")
            error_activity.status = "error"
            error_activity.ended_at = time.monotonic()
            self._append_line(f"Error: {event.get('error')}")
        elif event_type == "hook_debug":
            text = str(event.get("text") or "").strip()
            if text:
                self._append_line(text)
        elif event_type == "turn_complete":
            self._close_assistant_block()
            self.state.on_turn_complete()
        self._refresh_hint()
        self.app.invalidate()

    def _append_assistant(self, text: str) -> None:
        self.state.on_assistant_text()
        if not self._assistant_started_in_turn:
            self._finish_activity(self._model_wait_seq, status="done")
            self._stream_seq = self._start_activity("模型流式输出中").seq
            self._assistant_started_in_turn = True
            self._assistant_streaming_cursor = True
        if not self._assistant_block_open:
            if self._transcript_chunks and self._transcript_last_char() not in {None, "\n"}:
                self._append_transcript_text("\n", style="class:transcript.system")
            self._assistant_chunk_index = len(self._transcript_chunks)
            self._transcript_chunks.append(
                TranscriptChunk(style="class:assistant.pending", text="")
            )
            self._assistant_block_open = True

        if self._assistant_chunk_index is not None:
            chunk = self._transcript_chunks[self._assistant_chunk_index]
            chunk.text += text
            self._advance_transcript_cursor(text)
        else:
            self._append_transcript_text(text, style="class:assistant.pending")
        self._refresh_hint()
        self.app.invalidate()

    def _close_assistant_block(self, finalize: bool = True) -> None:
        if not self._assistant_block_open:
            return
        if self._assistant_chunk_index is None:
            self._assistant_block_open = False
            return
        chunk = self._transcript_chunks[self._assistant_chunk_index]
        if chunk.text and not chunk.text.endswith("\n"):
            chunk.text += "\n"
            self._advance_transcript_cursor("\n")
        if finalize:
            chunk.style = "class:assistant"
        self._assistant_block_open = False
        self._assistant_chunk_index = None
        if self._assistant_streaming_cursor:
            self._assistant_streaming_cursor = False

    def _append_user_block(self, text: str) -> None:
        self._close_assistant_block(finalize=True)
        lines = text.splitlines() or [""]
        if not lines:
            return
        if self._transcript_last_char() not in {None, "\n"}:
            self._append_transcript_text("\n", style="class:transcript.system")
        self._append_transcript_text("\n", style="class:transcript.system")
        for line in lines:
            self._append_transcript_text(f"> {line}\n", style="class:user")

    def _append_line(self, line: str, style: str = "class:transcript.system") -> None:
        self._close_assistant_block(finalize=False)
        self._append_transcript_text(line + "\n", style=style)
