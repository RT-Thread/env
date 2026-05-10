"""Utility helpers."""

from eagent.utils.completer import SlashCommandCompleter, build_completer
from eagent.utils.cost import create_cost_tracker, format_token_count, format_usd, summarize_cost
from eagent.utils.format import blue, bold, dim, gold, green, red, yellow
from eagent.utils.process import ProcessResult, run_process
from eagent.utils.streaming import collect_assistant_text, event_to_log_line

__all__ = [
    "blue",
    "green",
    "yellow",
    "red",
    "dim",
    "bold",
    "gold",
    "ProcessResult",
    "run_process",
    "create_cost_tracker",
    "format_token_count",
    "format_usd",
    "summarize_cost",
    "SlashCommandCompleter",
    "build_completer",
    "collect_assistant_text",
    "event_to_log_line",
]
