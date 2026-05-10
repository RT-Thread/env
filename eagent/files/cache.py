"""LRU file state cache."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from eagent.core.types import FileState

MAX_ENTRIES = 100
MAX_TOTAL_BYTES = 25 * 1024 * 1024


class LruFileStateCache:
    def __init__(
        self, max_entries: int = MAX_ENTRIES, max_total_bytes: int = MAX_TOTAL_BYTES
    ) -> None:
        self._max_entries = max_entries
        self._max_total_bytes = max_total_bytes
        self._store: OrderedDict[str, tuple[FileState, int]] = OrderedDict()
        self._bytes = 0

    def _key(self, path: str) -> str:
        return str(Path(path).expanduser().resolve())

    def _size(self, state: FileState) -> int:
        return len(state.content.encode("utf-8"))

    def _evict(self) -> None:
        while self._store and (
            len(self._store) > self._max_entries or self._bytes > self._max_total_bytes
        ):
            _k, (_s, b) = self._store.popitem(last=False)
            self._bytes -= b

    def get(self, path: str) -> FileState | None:
        key = self._key(path)
        item = self._store.get(key)
        if item is None:
            return None
        self._store.move_to_end(key)
        return item[0]

    def set(self, path: str, state: FileState) -> None:
        key = self._key(path)
        old = self._store.pop(key, None)
        if old:
            self._bytes -= old[1]
        size = self._size(state)
        self._store[key] = (state, size)
        self._bytes += size
        self._evict()

    def has(self, path: str) -> bool:
        return self._key(path) in self._store

    def delete(self, path: str) -> None:
        key = self._key(path)
        old = self._store.pop(key, None)
        if old:
            self._bytes -= old[1]

    def keys(self):
        return list(self._store.keys())

    def clone(self) -> LruFileStateCache:
        cloned = LruFileStateCache(self._max_entries, self._max_total_bytes)
        for key, (state, _bytes) in self._store.items():
            cloned.set(
                key,
                FileState(
                    content=state.content,
                    timestamp=state.timestamp,
                    offset=state.offset,
                    limit=state.limit,
                    is_partial_view=state.is_partial_view,
                ),
            )
        return cloned

    def merge(self, other) -> None:
        for key in other.keys():
            other_state = other.get(key)
            if other_state is None:
                continue
            current = self.get(key)
            if current is None or other_state.timestamp > current.timestamp:
                self.set(key, other_state)

    @property
    def size(self) -> int:
        return len(self._store)


def create_file_state_cache() -> LruFileStateCache:
    return LruFileStateCache()
