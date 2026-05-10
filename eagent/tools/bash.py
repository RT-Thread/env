"""Bash tool."""

from __future__ import annotations

import asyncio
import contextlib
import os
from asyncio.subprocess import PIPE
from typing import Any

from eagent.core.types import Tool, ToolContext, ToolResult
from eagent.tools.bash_readonly import is_read_only_command

DEFAULT_TIMEOUT_SECONDS = 120
MAX_TIMEOUT_SECONDS = 600
MAX_RESULT_SIZE_CHARS = 30_000
MAX_BUFFER_SIZE = 10 * 1024 * 1024


async def _execute(command: str, cwd: str, timeout_s: int) -> tuple[str, str, int, bool]:
    process = await asyncio.create_subprocess_exec(
        "bash",
        "-c",
        command,
        cwd=cwd,
        stdout=PIPE,
        stderr=PIPE,
        env={
            **os.environ,
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "TERM": os.environ.get("TERM", "xterm-256color"),
            "GIT_PAGER": "cat",
            "PAGER": "cat",
        },
    )

    timed_out = False
    try:
        stdout_b, stderr_b = await asyncio.wait_for(process.communicate(), timeout=timeout_s)
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
        timed_out = True
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2)
        except TimeoutError:
            process.kill()
            await process.wait()
        stdout_b, stderr_b = b"", b"[command timed out]"

    stdout = stdout_b.decode("utf-8", errors="replace")[:MAX_BUFFER_SIZE]
    stderr = stderr_b.decode("utf-8", errors="replace")[:MAX_BUFFER_SIZE]
    code = process.returncode or 0
    return stdout, stderr, code, timed_out


def _format_output(stdout: str, stderr: str, code: int, timed_out: bool) -> str:
    parts: list[str] = []
    if timed_out:
        parts.append("[Command timed out]")

    if stdout:
        if len(stdout) > MAX_RESULT_SIZE_CHARS:
            parts.append(stdout[:MAX_RESULT_SIZE_CHARS])
            parts.append(f"\n[stdout truncated: {len(stdout)} chars total]")
        else:
            parts.append(stdout)

    if stderr and stderr.strip():
        cap = MAX_RESULT_SIZE_CHARS // 3
        if len(stderr) > cap:
            parts.append(f"\nSTDERR:\n{stderr[:cap]}")
            parts.append(f"[stderr truncated: {len(stderr)} chars total]")
        else:
            parts.append(f"\nSTDERR:\n{stderr}")

    if not parts:
        return "(No output)" if code == 0 else f"(No output, exit code: {code})"

    if code != 0 and not timed_out:
        parts.append(f"\n(exit code: {code})")
    return "".join(parts)


async def _call(input_data: dict[str, Any], context: ToolContext) -> ToolResult:
    command = str(input_data.get("command") or "").strip()
    if not command:
        return ToolResult(result="Error: command cannot be empty.", is_error=True)

    timeout = int(input_data.get("timeout") or DEFAULT_TIMEOUT_SECONDS)
    timeout = max(1, min(timeout, MAX_TIMEOUT_SECONDS))

    try:
        stdout, stderr, code, timed_out = await _execute(command, context.cwd, timeout)
        result = _format_output(stdout, stderr, code, timed_out)
        return ToolResult(result=result, is_error=(code != 0 and not timed_out))
    except Exception as exc:
        return ToolResult(result=f"Error executing command: {exc}", is_error=True)


def build_bash_tool() -> Tool:
    return Tool(
        name="Bash",
        description=(
            "Execute a bash command. Use for running scripts, searching code, "
            "checking file status, and tests."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "minimum": 1, "maximum": MAX_TIMEOUT_SECONDS},
                "description": {"type": "string"},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        call=_call,
        prompt=lambda: (
            "Execute bash commands in the working directory. "
            "Prefer non-interactive commands and include timeout for long operations."
        ),
        is_read_only=lambda input_data: is_read_only_command(str(input_data.get("command") or "")),
        is_concurrency_safe=lambda input_data: is_read_only_command(
            str(input_data.get("command") or "")
        ),
        max_result_size_chars=MAX_RESULT_SIZE_CHARS,
        user_facing_name=lambda input_data: f"Bash: {str(input_data.get('command') or '')[:60]}",
    )
