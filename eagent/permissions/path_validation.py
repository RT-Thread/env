"""Path safety validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DANGEROUS_ABS = (
    "/",
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/var",
    "/boot",
    "/dev",
    "/proc",
    "/sys",
)


def _dangerous_home_paths() -> tuple[str, ...]:
    home = str(Path.home())
    return (
        os.path.join(home, ".ssh"),
        os.path.join(home, ".aws"),
        os.path.join(home, ".gnupg"),
        os.path.join(home, ".config"),
    )


def _dangerous_match(path: str) -> str | None:
    for prefix in DANGEROUS_ABS:
        if path == prefix or (prefix != "/" and path.startswith(prefix + os.sep)):
            return prefix
    for prefix in _dangerous_home_paths():
        if path == prefix or path.startswith(prefix + os.sep):
            return prefix
    return None


def _resolve_symlink(path: Path) -> Path:
    try:
        return path.resolve(strict=True)
    except Exception:
        try:
            return path.parent.resolve(strict=True) / path.name
        except Exception:
            return path.resolve(strict=False)


@dataclass(frozen=True)
class PathValidationResult:
    allowed: bool
    message: str | None = None


async def validate_path(file_path: str, project_root: str) -> PathValidationResult:
    resolved = str(Path(file_path).expanduser().resolve(strict=False))
    danger = _dangerous_match(resolved)
    if danger:
        return PathValidationResult(
            False, f'Access denied: "{resolved}" is within dangerous path "{danger}".'
        )

    real = str(_resolve_symlink(Path(resolved)))
    if real != resolved:
        danger2 = _dangerous_match(real)
        if danger2:
            return PathValidationResult(
                False,
                f'Access denied: "{resolved}" resolves to dangerous path "{real}" under "{danger2}".',
            )

    root = str(Path(project_root).expanduser().resolve(strict=False))
    if real != root and not real.startswith(root + os.sep):
        return PathValidationResult(
            True, f'Warning: "{resolved}" is outside project root "{root}".'
        )

    return PathValidationResult(True)
