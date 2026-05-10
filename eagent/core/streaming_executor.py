"""Streaming tool executor with safe parallel batching."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, Literal

from eagent.core.types import StreamEvent, Tool, ToolContext, ToolResult, ToolUseBlock

MAX_CONCURRENCY = 10


@dataclass
class QueuedTool:
    block: ToolUseBlock
    tool: Tool
    is_safe: bool
    result: ToolResult | None = None
    hook_debug_lines: list[str] = field(default_factory=list)


@dataclass
class ToolBatch:
    is_concurrency_safe: bool
    items: list[QueuedTool]


def _partition_tool_calls(items: list[QueuedTool]) -> list[ToolBatch]:
    batches: list[ToolBatch] = []
    current_safe: list[QueuedTool] = []

    for item in items:
        if item.is_safe:
            current_safe.append(item)
            continue

        if current_safe:
            batches.append(ToolBatch(is_concurrency_safe=True, items=current_safe))
            current_safe = []
        batches.append(ToolBatch(is_concurrency_safe=False, items=[item]))

    if current_safe:
        batches.append(ToolBatch(is_concurrency_safe=True, items=current_safe))
    return batches


async def _execute_single(item: QueuedTool, context: ToolContext) -> ToolResult:
    def _append_prompt_appends(values: list[str]) -> None:
        if not values or context.on_hook_prompt_append is None:
            return
        for value in values:
            context.on_hook_prompt_append(value)

    async def _run_hooks(
        event: Literal["pre_tool_use", "post_tool_use", "on_error"],
        *,
        target: str,
        variables: dict[str, Any],
        allow_prompt_append: bool = True,
    ) -> tuple[bool, str | None]:
        runtime = context.hook_runtime
        if runtime is None:
            return False, None

        outcome = await runtime.run(
            event,
            target=target,
            variables=variables,
            cwd=context.cwd,
            dev_mode=context.dev_mode,
            allow_prompt_append=allow_prompt_append,
        )
        item.hook_debug_lines.extend(outcome.debug_lines)
        _append_prompt_appends(outcome.prompt_appends)
        return outcome.aborted, outcome.abort_reason

    target_name = item.block.name
    base_vars: dict[str, Any] = {
        "tool_name": item.block.name,
        "tool_use_id": item.block.id,
        "tool_input": str(item.block.input),
        "session_id": context.session_id,
    }

    try:
        before_aborted, before_reason = await _run_hooks(
            "pre_tool_use",
            target=target_name,
            variables=base_vars,
            allow_prompt_append=True,
        )
        if before_aborted:
            result = ToolResult(
                result=before_reason or f"Hook aborted before {item.block.name}.",
                is_error=True,
            )
            item.result = result
            await _run_hooks(
                "on_error",
                target=target_name,
                variables={
                    **base_vars,
                    "source": "pre_tool_use",
                    "error": result.result,
                },
                allow_prompt_append=True,
            )
            return result

        result = await item.tool.call(item.block.input, context)
        if len(result.result) > item.tool.max_result_size_chars:
            result.result = (
                result.result[: item.tool.max_result_size_chars]
                + "\n\n[Output truncated: was "
                + f"{len(result.result)} chars, "
                + f"limit {item.tool.max_result_size_chars}]"
            )

        after_aborted, after_reason = await _run_hooks(
            "post_tool_use",
            target=target_name,
            variables={
                **base_vars,
                "tool_result": result.result,
                "tool_is_error": result.is_error,
            },
            allow_prompt_append=True,
        )
        if after_aborted:
            result = ToolResult(
                result=after_reason or f"Hook aborted after {item.block.name}.",
                is_error=True,
            )

        if result.is_error:
            await _run_hooks(
                "on_error",
                target=target_name,
                variables={
                    **base_vars,
                    "source": "tool_result",
                    "error": result.result,
                    "tool_result": result.result,
                },
                allow_prompt_append=True,
            )

        item.result = result
        return result
    except Exception as exc:
        result = ToolResult(result=f"Error executing {item.block.name}: {exc}", is_error=True)
        await _run_hooks(
            "on_error",
            target=target_name,
            variables={
                **base_vars,
                "source": "tool_exception",
                "error": str(exc),
            },
            allow_prompt_append=True,
        )
        item.result = result
        return result


async def _execute_parallel_batch(
    batch: ToolBatch, context: ToolContext
) -> AsyncGenerator[StreamEvent, None]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async def run(item: QueuedTool) -> ToolResult:
        async with semaphore:
            return await _execute_single(item, context)

    tasks: list[asyncio.Task[ToolResult]] = []
    for item in batch.items:
        yield {
            "type": "tool_start",
            "tool_use_id": item.block.id,
            "tool_name": item.block.name,
            "input": item.block.input,
        }
        tasks.append(asyncio.create_task(run(item)))

    # Preserve original order in emitted results.
    for item, task in zip(batch.items, tasks, strict=True):
        await task
        assert item.result is not None
        if context.dev_mode and item.hook_debug_lines:
            for line in item.hook_debug_lines:
                yield {"type": "hook_debug", "text": line}
        yield {
            "type": "tool_result",
            "tool_use_id": item.block.id,
            "tool_name": item.block.name,
            "result": item.result.result,
            "is_error": item.result.is_error,
        }


async def _execute_serial_batch(
    batch: ToolBatch, context: ToolContext
) -> AsyncGenerator[StreamEvent, None]:
    item = batch.items[0]
    yield {
        "type": "tool_start",
        "tool_use_id": item.block.id,
        "tool_name": item.block.name,
        "input": item.block.input,
    }
    await _execute_single(item, context)
    assert item.result is not None
    if context.dev_mode and item.hook_debug_lines:
        for line in item.hook_debug_lines:
            yield {"type": "hook_debug", "text": line}
    yield {
        "type": "tool_result",
        "tool_use_id": item.block.id,
        "tool_name": item.block.name,
        "result": item.result.result,
        "is_error": item.result.is_error,
    }


def _unknown_tool(name: str) -> Tool:
    async def _call(_input, _context):
        return ToolResult(result=f"Unknown tool: {name}", is_error=True)

    return Tool(
        name=name,
        description="",
        input_schema={"type": "object"},
        call=_call,
        prompt=lambda: "",
        is_concurrency_safe=lambda _i: False,
        is_read_only=lambda _i: False,
        max_result_size_chars=30_000,
        user_facing_name=lambda _i: name,
    )


async def execute_tools(
    tool_use_blocks: list[ToolUseBlock],
    tools: list[Tool],
    context: ToolContext,
) -> AsyncGenerator[StreamEvent, None]:
    tool_map = {tool.name: tool for tool in tools}

    queue: list[QueuedTool] = []
    for block in tool_use_blocks:
        tool = tool_map.get(block.name) or _unknown_tool(block.name)
        queue.append(
            QueuedTool(
                block=block,
                tool=tool,
                is_safe=bool(tool.is_concurrency_safe(block.input)),
            )
        )

    for batch in _partition_tool_calls(queue):
        if batch.is_concurrency_safe:
            async for event in _execute_parallel_batch(batch, context):
                yield event
        else:
            async for event in _execute_serial_batch(batch, context):
                yield event


async def execute_tools_collect(
    tool_use_blocks: list[ToolUseBlock],
    tools: list[Tool],
    context: ToolContext,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    async for event in execute_tools(tool_use_blocks, tools, context):
        if event["type"] == "tool_result":
            results.append(
                {
                    "tool_use_id": event["tool_use_id"],
                    "tool_name": event["tool_name"],
                    "result": ToolResult(result=event["result"], is_error=event["is_error"]),
                }
            )
    return results
