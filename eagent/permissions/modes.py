"""Permission mode metadata."""

from __future__ import annotations

from dataclasses import dataclass

from eagent.core.types import PermissionMode

MODE_DESCRIPTIONS: dict[PermissionMode, str] = {
    "default": "Default mode: write operations and mutating shell commands require confirmation.",
    "plan": "Plan mode: read-only mode with no write operations.",
    "acceptEdits": "Accept-edits mode: file edits are allowed, shell mutations still require confirmation.",
    "bypassPermissions": "Bypass mode: all actions are auto-approved.",
}


@dataclass(frozen=True)
class ModeRestrictions:
    allow_reads: bool
    allow_writes: bool
    allow_bash: bool


MODE_RESTRICTIONS: dict[PermissionMode, ModeRestrictions] = {
    "default": ModeRestrictions(allow_reads=True, allow_writes=False, allow_bash=False),
    "plan": ModeRestrictions(allow_reads=True, allow_writes=False, allow_bash=False),
    "acceptEdits": ModeRestrictions(allow_reads=True, allow_writes=True, allow_bash=False),
    "bypassPermissions": ModeRestrictions(allow_reads=True, allow_writes=True, allow_bash=True),
}


def get_mode_description(mode: PermissionMode) -> str:
    return MODE_DESCRIPTIONS.get(mode, f"Unknown mode: {mode}")


def get_mode_restrictions(mode: PermissionMode) -> ModeRestrictions:
    return MODE_RESTRICTIONS.get(mode, MODE_RESTRICTIONS["default"])
