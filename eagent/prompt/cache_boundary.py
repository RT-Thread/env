"""Prompt cache boundary helpers."""

from __future__ import annotations

from eagent.core.types import SystemPromptBlock

SYSTEM_PROMPT_DYNAMIC_BOUNDARY = "__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__"


def split_system_blocks(
    blocks: list[SystemPromptBlock],
) -> tuple[list[SystemPromptBlock], list[SystemPromptBlock]]:
    index = next((i for i, b in enumerate(blocks) if b.text == SYSTEM_PROMPT_DYNAMIC_BOUNDARY), -1)
    if index < 0:
        return list(blocks), []
    return blocks[:index], blocks[index + 1 :]


def apply_cache(blocks: list[SystemPromptBlock]) -> list[SystemPromptBlock]:
    static_blocks, dynamic_blocks = split_system_blocks(blocks)
    if not static_blocks:
        return dynamic_blocks

    out = [
        SystemPromptBlock(type="text", text=b.text, cache_control=b.cache_control)
        for b in static_blocks
    ]
    out[-1].cache_control = {"type": "ephemeral"}
    out.extend(dynamic_blocks)
    return out


def strip_boundary(blocks: list[SystemPromptBlock]) -> list[SystemPromptBlock]:
    return [b for b in blocks if b.text != SYSTEM_PROMPT_DYNAMIC_BOUNDARY]
