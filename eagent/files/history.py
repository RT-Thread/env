"""File history snapshot helpers."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from eagent.core.types import FileHistoryBackup, FileHistorySnapshot, FileHistoryState
from eagent.paths import env_root

MAX_SNAPSHOTS = 100


def _history_dir(session_id: str) -> Path:
    return env_root() / "file-history" / session_id


def _path_hash(file_path: str) -> str:
    return hashlib.sha256(file_path.encode("utf-8")).hexdigest()[:16]


def create_file_history_state() -> FileHistoryState:
    return FileHistoryState()


async def track_edit(state: FileHistoryState, file_path: str, session_id: str) -> None:
    _ = session_id
    state.tracked_files.add(str(Path(file_path).expanduser().resolve()))


async def make_snapshot(
    state: FileHistoryState, message_id: str, session_id: str
) -> FileHistorySnapshot:
    now = time.time()
    root = _history_dir(session_id)
    root.mkdir(parents=True, exist_ok=True)

    backups: dict[str, FileHistoryBackup] = {}
    for file_path in sorted(state.tracked_files):
        p = Path(file_path)

        version = 1
        for snap in reversed(state.snapshots):
            prev = snap.tracked_file_backups.get(file_path)
            if prev is not None:
                version = prev.version + 1
                break

        if p.exists() and p.is_file():
            backup_name = f"{_path_hash(file_path)}@v{version}"
            (root / backup_name).write_bytes(p.read_bytes())
            backups[file_path] = FileHistoryBackup(
                backup_file_name=backup_name,
                version=version,
                backup_time=now,
            )
        else:
            backups[file_path] = FileHistoryBackup(
                backup_file_name=None,
                version=version,
                backup_time=now,
            )

    snapshot = FileHistorySnapshot(
        message_id=message_id, tracked_file_backups=backups, timestamp=now
    )
    state.snapshots.append(snapshot)
    state.snapshot_sequence += 1
    if len(state.snapshots) > MAX_SNAPSHOTS:
        state.snapshots = state.snapshots[-MAX_SNAPSHOTS:]
    return snapshot


async def rewind(state: FileHistoryState, snapshot_index: int, session_id: str) -> None:
    if snapshot_index < 0 or snapshot_index >= len(state.snapshots):
        raise ValueError("Invalid snapshot index")

    target = state.snapshots[snapshot_index]
    root = _history_dir(session_id)
    for file_path, backup in target.tracked_file_backups.items():
        p = Path(file_path)
        if backup.backup_file_name is None:
            if p.exists():
                p.unlink()
            continue

        src = root / backup.backup_file_name
        if src.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(src.read_bytes())

    state.snapshots = state.snapshots[: snapshot_index + 1]


async def get_diff_stats(
    state: FileHistoryState,
    snapshot_a: int,
    snapshot_b: int,
    session_id: str,
) -> list[dict[str, int | str]]:
    if (
        snapshot_a < 0
        or snapshot_b < 0
        or snapshot_a >= len(state.snapshots)
        or snapshot_b >= len(state.snapshots)
    ):
        raise ValueError("Invalid snapshot index")

    root = _history_dir(session_id)
    a = state.snapshots[snapshot_a]
    b = state.snapshots[snapshot_b]
    files = set(a.tracked_file_backups) | set(b.tracked_file_backups)

    def _read(backup: FileHistoryBackup | None) -> str:
        if backup is None or backup.backup_file_name is None:
            return ""
        path = root / backup.backup_file_name
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")

    out: list[dict[str, int | str]] = []
    for file_path in sorted(files):
        left = _read(a.tracked_file_backups.get(file_path))
        right = _read(b.tracked_file_backups.get(file_path))
        if left == right:
            continue
        left_lines = set(left.splitlines())
        right_lines = set(right.splitlines())
        out.append(
            {
                "file": file_path,
                "insertions": len([x for x in right_lines if x not in left_lines]),
                "deletions": len([x for x in left_lines if x not in right_lines]),
            }
        )
    return out
