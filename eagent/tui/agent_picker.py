"""Agent profile picker state and rendering."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from prompt_toolkit.formatted_text import FormattedText


@dataclass
class AgentPicker:
    items: list[tuple[str, str]] = field(default_factory=list)
    index: int = 0
    future: asyncio.Future[str | None] | None = None

    @property
    def active(self) -> bool:
        return self.future is not None and not self.future.done()

    def open(self, items: list[tuple[str, str]], loop: asyncio.AbstractEventLoop) -> None:
        self.items = list(items)
        self.index = 0
        self.future = loop.create_future()

    async def wait(self) -> str | None:
        if self.future is None:
            return None
        return await self.future

    def close(self) -> None:
        self.future = None
        self.items = []
        self.index = 0

    def move(self, step: int) -> None:
        if not self.active or not self.items:
            return
        self.index = (self.index + step) % len(self.items)

    def confirm(self) -> None:
        if not self.active or not self.items or self.future is None:
            return
        self.future.set_result(self.items[self.index][0])

    def cancel(self) -> None:
        if self.future is None or self.future.done():
            return
        self.future.set_result(None)

    def render(self) -> FormattedText:
        if not self.active or not self.items:
            return FormattedText([])

        title = "Agent 配置列表（上下键移动，Enter 选择，Esc 取消）"
        rows = [title]
        rows.extend(
            f"{'>' if idx == self.index else ' '} {label}"
            for idx, (_name, label) in enumerate(self.items)
        )
        inner_width = min(76, max(len(row) for row in rows))

        def clip(text: str) -> str:
            if len(text) <= inner_width:
                return text
            if inner_width <= 3:
                return text[:inner_width]
            return text[: inner_width - 3] + "..."

        border = "+-" + "-" * inner_width + "-+\n"
        fragments: list[tuple[str, str]] = [("class:toolpanel.summary", border)]
        fragments.append(("class:toolpanel.summary", f"| {clip(title).ljust(inner_width)} |\n"))
        fragments.append(("class:toolpanel.summary", border))
        for idx, (_name, label) in enumerate(self.items):
            marker = ">" if idx == self.index else " "
            row_text = clip(f"{marker} {label}").ljust(inner_width)
            style = "class:toolpanel.summary" if idx == self.index else "class:toolpanel.detail"
            fragments.append((style, f"| {row_text} |\n"))
        fragments.append(("class:toolpanel.summary", border))
        return FormattedText(fragments)
