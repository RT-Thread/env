"""Context and session helpers."""

from eagent.context.agent_config import (
    AgentProfile,
    AgentProfileSet,
    get_agent_config_path,
    load_agent_profiles,
    save_agent_profiles,
    set_active_profile,
)
from eagent.context.compaction import CompactParams, CompactResult, compact, should_auto_compact
from eagent.context.git_context import get_git_context, get_git_status_short
from eagent.context.memory import has_agent_memory, load_agent_memory
from eagent.context.post_compact import create_post_compact_attachments
from eagent.context.session_store import (
    SessionSummary,
    init_session,
    list_session_summaries,
    list_session_summaries_sync,
    list_sessions,
    list_sessions_sync,
    load_session,
    save_message,
)
from eagent.context.token_counting import (
    estimate_json_tokens,
    estimate_message_tokens,
    estimate_single_message_tokens,
    estimate_system_prompt_tokens,
    estimate_tokens,
    truncate_to_token_budget,
)

__all__ = [
    "AgentProfile",
    "AgentProfileSet",
    "get_agent_config_path",
    "load_agent_profiles",
    "save_agent_profiles",
    "set_active_profile",
    "CompactParams",
    "CompactResult",
    "compact",
    "should_auto_compact",
    "get_git_context",
    "get_git_status_short",
    "has_agent_memory",
    "load_agent_memory",
    "create_post_compact_attachments",
    "SessionSummary",
    "init_session",
    "list_session_summaries",
    "list_session_summaries_sync",
    "list_sessions",
    "list_sessions_sync",
    "load_session",
    "save_message",
    "estimate_tokens",
    "estimate_json_tokens",
    "estimate_single_message_tokens",
    "estimate_message_tokens",
    "estimate_system_prompt_tokens",
    "truncate_to_token_budget",
]
