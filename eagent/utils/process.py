"""Async process helpers."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass


@dataclass
class ProcessResult:
    stdout: str
    stderr: str
    returncode: int


async def run_process(
    command: list[str],
    cwd: str | None = None,
    timeout: float | None = None,
) -> ProcessResult:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout_b, stderr_b = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.CancelledError:
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
        raise
    except TimeoutError:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2)
        except TimeoutError:
            process.kill()
            await process.wait()
        raise

    return ProcessResult(
        stdout=stdout_b.decode("utf-8", errors="replace"),
        stderr=stderr_b.decode("utf-8", errors="replace"),
        returncode=process.returncode or 0,
    )
