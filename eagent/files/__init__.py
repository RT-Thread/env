"""File state modules."""

from eagent.files.atomic_write import atomic_write
from eagent.files.cache import LruFileStateCache, create_file_state_cache
from eagent.files.history import (
    create_file_history_state,
    get_diff_stats,
    make_snapshot,
    rewind,
    track_edit,
)

__all__ = [
    "atomic_write",
    "LruFileStateCache",
    "create_file_state_cache",
    "create_file_history_state",
    "track_edit",
    "make_snapshot",
    "rewind",
    "get_diff_stats",
]
