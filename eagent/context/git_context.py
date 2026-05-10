"""Git context helper for prompts."""

from __future__ import annotations

import asyncio

_CACHE: dict[str, tuple[float, str]] = {}
_TTL = 300.0


async def _git(cwd: str, *args: str) -> str | None:
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        if proc.returncode != 0:
            return None
        return stdout.decode("utf-8", errors="replace").strip()
    except Exception:
        return None


async def get_git_context(cwd: str) -> str:
    import time

    now = time.time()
    cached = _CACHE.get(cwd)
    if cached and now - cached[0] < _TTL:
        return cached[1]

    inside = await _git(cwd, "rev-parse", "--is-inside-work-tree")
    if inside != "true":
        result = "Not a git repository."
        _CACHE[cwd] = (now, result)
        return result

    branch = await _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    status = await _git(cwd, "status", "--porcelain")
    log = await _git(cwd, "log", "--oneline", "-10")

    lines: list[str] = []
    if branch:
        lines.append(f"Current branch: {branch}")
    if status is not None:
        lines.append("Status: Clean working tree" if not status else f"Status:\n{status}")
    if log:
        lines.append(f"Recent commits:\n{log}")

    result = "\n\n".join(lines)
    _CACHE[cwd] = (now, result)
    return result


async def get_git_status_short(cwd: str) -> str:
    branch = await _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if not branch:
        return ""
    status = await _git(cwd, "status", "--porcelain")
    count = len([line for line in (status or "").splitlines() if line.strip()])
    return f"{branch} (clean)" if count == 0 else f"{branch} ({count} changed)"
