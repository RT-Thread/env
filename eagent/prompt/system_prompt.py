"""System prompt builder."""

from __future__ import annotations

import datetime as _dt
import os

from eagent.core.types import SystemPromptBlock
from eagent.prompt.cache_boundary import SYSTEM_PROMPT_DYNAMIC_BOUNDARY

_STATIC_PROMPT = """You are RTE-AI, a CLI coding assistant.
Be concise, safe, and action-oriented.
Use available tools to complete tasks.
Prefer dedicated tools over shell commands.
"""


def build_system_prompt_blocks(
    agent_memory: str, git_context: str, cwd: str, model: str
) -> list[SystemPromptBlock]:
    blocks: list[SystemPromptBlock] = [
        SystemPromptBlock(type="text", text=_STATIC_PROMPT.strip()),
        SystemPromptBlock(type="text", text=SYSTEM_PROMPT_DYNAMIC_BOUNDARY),
    ]

    if agent_memory.strip():
        blocks.append(
            SystemPromptBlock(
                type="text",
                text=f"## Memory\n<agent_memory>\n{agent_memory.strip()}\n</agent_memory>",
            )
        )

    blocks.append(
        SystemPromptBlock(
            type="text",
            text=(
                "## Environment\n"
                f"- Working directory: {cwd}\n"
                f"- Model: {model}\n"
                f"- Platform: {os.name}\n"
                f"- Date: {_dt.date.today().isoformat()}"
            ),
        )
    )

    if git_context.strip():
        blocks.append(
            SystemPromptBlock(
                type="text",
                text=f"## Git Status\n<git-status>\n{git_context.strip()}\n</git-status>",
            )
        )

    return blocks
