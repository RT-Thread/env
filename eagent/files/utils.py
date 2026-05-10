"""File utility helpers used by tools and permissions."""

from __future__ import annotations

import os
from pathlib import Path


def normalize_path(path: str) -> str:
    return str(Path(path).expanduser().resolve())


def normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n")


def is_within_project(file_path: str, project_root: str) -> bool:
    file_abs = Path(file_path).expanduser().resolve()
    root_abs = Path(project_root).expanduser().resolve()
    return file_abs == root_abs or root_abs in file_abs.parents


def detect_encoding(data: bytes) -> str:
    if len(data) >= 2 and data[0] == 0xFF and data[1] == 0xFE:
        return "utf-16le"
    if len(data) >= 3 and data[0] == 0xEF and data[1] == 0xBB and data[2] == 0xBF:
        return "utf-8-sig"
    return "utf-8"


def is_binary_data(data: bytes) -> bool:
    sample = data[:8192]
    return b"\x00" in sample


def is_binary_file(file_path: str) -> bool:
    path = Path(file_path)
    try:
        data = path.read_bytes()[:8192]
        return is_binary_data(data)
    except Exception:
        return False


def format_with_line_numbers(text: str, start_line: int = 1) -> str:
    lines = text.split("\n")
    width = len(str(start_line + len(lines) - 1)) if lines else 1
    return "\n".join(f"{str(i).rjust(width)}\t{line}" for i, line in enumerate(lines, start_line))


def get_file_size(file_path: str) -> int:
    try:
        return os.path.getsize(file_path)
    except OSError:
        return -1
