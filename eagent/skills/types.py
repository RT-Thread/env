"""Types for skills subsystem."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal


@dataclass
class SkillDefinition:
    name: str
    description: str
    when_to_use: str | None = None
    argument_hint: str | None = None
    argument_names: list[str] | None = None
    allowed_tools: list[str] | None = None
    model: str | None = None
    user_invocable: bool = True
    context: Literal["inline", "fork"] = "inline"
    agent: str | None = None
    paths: list[str] | None = None
    skill_root: str | None = None
    get_prompt: Callable[[str], Awaitable[str]] | None = None


SkillSource = Literal["user", "project"]


@dataclass
class SkillLoadResult:
    skill: SkillDefinition
    source: SkillSource
    file_path: str
