"""Post-compact file attachment refresh."""

from __future__ import annotations

from eagent.core.types import Message


async def create_post_compact_attachments(
    preserved_messages: list[Message], read_file_state, context_budget: int = 50_000
) -> list[Message]:
    _ = preserved_messages
    _ = read_file_state
    _ = context_budget
    # Simplified placeholder: keep behavior optional.
    return []
