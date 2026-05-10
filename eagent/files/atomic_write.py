"""Atomic file write helper."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _file_mode(path: Path) -> int | None:
    try:
        return path.stat().st_mode
    except OSError:
        return None


def atomic_write(file_path: str, content: str) -> None:
    target = Path(file_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    original_mode = _file_mode(target)

    tmp_fd, tmp_name = tempfile.mkstemp(prefix=f"{target.name}.tmp.", dir=str(target.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(content)
        if original_mode is not None:
            try:
                os.chmod(tmp, original_mode)
            except OSError:
                pass

        try:
            os.replace(tmp, target)
        except OSError:
            target.write_text(content, encoding="utf-8")
            if original_mode is not None:
                try:
                    os.chmod(target, original_mode)
                except OSError:
                    pass
            if tmp.exists():
                tmp.unlink()
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise
