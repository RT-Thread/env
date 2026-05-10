"""Status bar rendering for the agent TUI."""

from __future__ import annotations

import os
from dataclasses import dataclass

from prompt_toolkit.formatted_text import FormattedText

SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


@dataclass(frozen=True)
class StatusMeta:
    model: str
    cwd: str = ""
    git: str = ""


@dataclass(frozen=True)
class StatusBarState:
    columns: int
    busy: bool
    status: str
    status_text: str
    input_mode: str
    spinner_index: int
    running_activity_count: int
    tool_text: str | None
    tool_running: bool
    tool_error: bool
    activity_compact_mode: bool
    queued_input_count: int
    meta: StatusMeta


class StatusBarRenderer:
    def render(self, state: StatusBarState) -> FormattedText:
        show_spinner = state.busy or state.running_activity_count > 0 or state.tool_running
        spinner = SPINNER_FRAMES[state.spinner_index] if show_spinner else "•"
        mode = "HISTORY" if state.input_mode == "history_view" else "EDIT"
        activity_mode = "ACT:min" if state.activity_compact_mode else "ACT:full"
        compact_idle = (
            not state.busy
            and state.status == "idle"
            and state.input_mode == "compose"
            and state.queued_input_count == 0
        )
        fragments: list[tuple[str, str]] = [
            ("class:brand.rte", " RTE"),
            ("class:brand.hyphen", "-"),
            ("class:brand.ai", "AI "),
            ("class:title", f"{spinner} {state.status_text} "),
            ("class:dim", " | "),
        ]

        if state.tool_text:
            tool_icon = (
                SPINNER_FRAMES[state.spinner_index]
                if state.tool_running
                else "!"
                if state.tool_error
                else "✓"
            )
            tool_style = "class:tool" if state.tool_running else "class:meta"
            fragments.extend(
                [
                    (tool_style, f"{tool_icon} {state.tool_text} "),
                    ("class:dim", " | "),
                ]
            )

        fragments.append(("class:meta", state.meta.model))
        used_width = sum(len(text) for _style, text in fragments)

        extras: list[tuple[str, str]] = []
        if state.columns >= 96 and state.meta.cwd:
            path_budget = max(12, min(40, state.columns - used_width - 24))
            extras.extend(
                [
                    ("class:dim", " | "),
                    ("class:meta", self.shorten_path(state.meta.cwd, path_budget)),
                ]
            )
        if state.columns >= 118 and state.meta.git:
            extra_width = sum(len(text) for _style, text in extras)
            git_budget = max(10, min(28, state.columns - used_width - extra_width - 8))
            extras.extend(
                [
                    ("class:dim", " | "),
                    ("class:meta", self.clip_text(state.meta.git, git_budget)),
                ]
            )
        fragments.extend(extras)

        if not compact_idle and state.columns >= 72:
            fragments.extend(
                [
                    ("class:dim", " | "),
                    ("class:meta", mode),
                    ("class:dim", " | "),
                    ("class:meta", activity_mode),
                ]
            )
        if state.queued_input_count:
            fragments.extend(
                [
                    ("class:dim", " | "),
                    ("class:meta", f"Q:{state.queued_input_count}"),
                ]
            )
        return FormattedText(fragments)

    @staticmethod
    def clip_text(text: str, max_width: int) -> str:
        if max_width <= 0:
            return ""
        if len(text) <= max_width:
            return text
        if max_width <= 3:
            return text[:max_width]
        return text[: max_width - 1] + "…"

    @staticmethod
    def shorten_path(path: str, max_width: int) -> str:
        if max_width <= 0:
            return ""
        home = os.path.expanduser("~")
        display = path
        if display == home:
            display = "~"
        elif display.startswith(home + os.sep):
            display = "~" + display[len(home) :]
        if len(display) <= max_width:
            return display
        if max_width <= 4:
            return display[-max_width:]
        return "…" + display[-(max_width - 1) :]
