"""Cost tracker helpers."""

from __future__ import annotations

from eagent.core.types import CostTracker


def format_token_count(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def format_usd(value: float) -> str:
    if value < 0.001:
        return f"${value:.5f}"
    if value < 0.01:
        return f"${value:.4f}"
    if value < 1:
        return f"${value:.3f}"
    return f"${value:.2f}"


def create_cost_tracker() -> CostTracker:
    return CostTracker()


def summarize_cost(tracker: CostTracker, model_config) -> str:
    in_str = format_token_count(tracker.total_input_tokens)
    out_str = format_token_count(tracker.total_output_tokens)
    cost_str = format_usd(tracker.total_cost_usd(model_config))
    parts = [f"Turn {tracker.turns}", f"{in_str} in / {out_str} out"]
    if tracker.total_cache_read_tokens > 0 or tracker.total_cache_creation_tokens > 0:
        cache_read = format_token_count(tracker.total_cache_read_tokens)
        cache_write = format_token_count(tracker.total_cache_creation_tokens)
        parts.append(f"cache: {cache_read} read / {cache_write} write")
    parts.append(cost_str)
    return " | ".join(parts)
