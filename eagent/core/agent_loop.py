"""Core agent orchestration loop."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

from eagent.context.compaction import CompactParams
from eagent.context.compaction import compact as compact_messages
from eagent.context.token_counting import estimate_message_tokens
from eagent.core.api_client import call_model, get_model_config
from eagent.core.errors import AbortError, PromptTooLongError, classify_error
from eagent.core.streaming_executor import execute_tools
from eagent.core.types import (
    ContentBlock,
    Message,
    QueryParams,
    StreamEvent,
    SystemPromptBlock,
    TextBlock,
    ToolContext,
    ToolResult,
    ToolResultBlock,
    ToolUseBlock,
)
from eagent.permissions.engine import PermissionContext, check_permission

AUTOCOMPACT_BUFFER_TOKENS = 13_000
MAX_PTL_RETRIES = 3
MICRO_COMPACT_THRESHOLD_CHARS = 50_000


def _should_auto_compact(
    messages: list[Message], context_window: int, max_output_tokens: int
) -> bool:
    threshold = context_window - max_output_tokens - AUTOCOMPACT_BUFFER_TOKENS
    return estimate_message_tokens(messages) > threshold


def _micro_compact_messages(messages: list[Message]) -> None:
    threshold_index = max(0, len(messages) - 6)
    for i in range(threshold_index):
        message = messages[i]
        if message.role != "user":
            continue
        for idx, block in enumerate(message.content):
            if getattr(block, "type", None) != "tool_result":
                continue
            content = block.content if isinstance(block.content, str) else str(block.content)
            if len(content) > MICRO_COMPACT_THRESHOLD_CHARS:
                message.content[idx] = ToolResultBlock(
                    type="tool_result",
                    tool_use_id=block.tool_use_id,
                    content=(
                        content[:5000]
                        + f"\n\n[Content truncated: was {len(content)} chars. Re-read if needed.]"
                    ),
                    is_error=block.is_error,
                )


def _truncate_for_ptl(messages: list[Message]) -> list[Message]:
    if len(messages) <= 2:
        return messages
    truncated = list(messages)
    del truncated[:2]
    return truncated


def _assistant_message(content: list[ContentBlock]) -> Message:
    return Message(role="assistant", content=content, id=str(uuid.uuid4()))


def _tool_result_message(results: list[tuple[str, ToolResult]]) -> Message:
    return Message(
        role="user",
        content=[
            ToolResultBlock(
                type="tool_result",
                tool_use_id=tool_use_id,
                content=result.result,
                is_error=result.is_error,
            )
            for tool_use_id, result in results
        ],
        id=str(uuid.uuid4()),
    )


def _hook_prompt_message(prompt: str) -> Message:
    return Message(
        role="user",
        content=[TextBlock(type="text", text=prompt)],
        id=str(uuid.uuid4()),
    )


def _describe_tool_use(tool_use: ToolUseBlock) -> str:
    input_data = tool_use.input
    if tool_use.name == "Bash":
        command = input_data.get("command") or "(no command)"
        return f"Bash: {command}"
    file_path = input_data.get("file_path") or input_data.get("path") or input_data.get("filePath")
    if file_path:
        return f"{tool_use.name}: {file_path}"
    return f"{tool_use.name}: {str(input_data)[:200]}"


async def _perform_compaction(
    messages: list[Message], params: QueryParams
) -> tuple[list[Message], int, int]:
    async def _call_model_for_compact(
        system_prompt: str, prompt: str, model: str, api_key: str
    ) -> str:
        effective_api_key = params.api_key_override or api_key
        synthetic_message = Message(role="user", content=[TextBlock(type="text", text=prompt)])
        model_config = get_model_config(model)
        text_parts: list[str] = []
        async for event in call_model(
            messages=[synthetic_message],
            tools=[],
            model_config=model_config,
            system_prompt_blocks=[SystemPromptBlock(type="text", text=system_prompt)],
            api_key=effective_api_key,
            api_base_url=params.api_base_url,
        ):
            if event["type"] == "assistant_text":
                text_parts.append(event["text"])
        return "".join(text_parts)

    result = await compact_messages(
        messages,
        CompactParams(
            api_key=params.api_key,
            model=params.model_config.model,
            system_prompt_blocks=params.system_prompt_blocks,
        ),
        _call_model_for_compact,
    )
    return result.compacted, result.old_tokens, result.new_tokens


async def _check_tool_permission(
    tool_use: ToolUseBlock, params: QueryParams, context: ToolContext
) -> tuple[bool, str | None]:
    tool = next((t for t in params.tools if t.name == tool_use.name), None)
    if tool is None:
        return True, None

    # Evaluate rule engine first.
    decision = await check_permission(
        tool_use.name,
        tool_use.input,
        PermissionContext(
            cwd=params.cwd, permission_mode=params.permission_mode, tools=params.tools
        ),
    )

    if decision.behavior == "deny":
        return False, decision.message or f"Permission denied for {tool_use.name}."
    if decision.behavior == "allow":
        return True, None

    # Fallback to runtime permission callback.
    user_decision = await params.on_permission_request(
        tool_use.name,
        tool_use.input,
        _describe_tool_use(tool_use),
    )
    return user_decision.behavior == "allow", user_decision.message


async def agent_loop(params: QueryParams) -> AsyncGenerator[StreamEvent, None]:
    messages = params.messages
    turn_count = 0
    ptl_retries = 0
    hook_prompt_appends: list[str] = []

    tool_context = ToolContext(
        cwd=params.cwd,
        read_file_state=params.read_file_state,
        file_history=params.file_history,
        modified_files=set(),
        session_id=params.session_id,
        abort_signal=params.abort_signal,
        permission_mode=params.permission_mode,
        on_permission_request=params.on_permission_request,
        hook_runtime=params.hook_runtime,
        on_hook_prompt_append=hook_prompt_appends.append,
        dev_mode=params.dev_mode,
    )

    async def _run_on_error_hooks(
        *,
        target: str,
        source: str,
        error_value: Any,
        extra: dict[str, Any] | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        if params.hook_runtime is None:
            return

        variables: dict[str, Any] = {
            "source": source,
            "target": target,
            "error": str(error_value),
            "session_id": params.session_id,
        }
        if extra:
            variables.update(extra)

        outcome = await params.hook_runtime.run(
            "on_error",
            target=target,
            variables=variables,
            cwd=params.cwd,
            dev_mode=params.dev_mode,
        )
        if params.dev_mode:
            for line in outcome.debug_lines:
                yield {"type": "hook_debug", "text": line}
        if outcome.prompt_appends:
            for prompt in outcome.prompt_appends:
                messages.append(_hook_prompt_message(prompt))

    while True:
        if getattr(params.abort_signal, "aborted", False):
            yield {"type": "error", "error": AbortError("Aborted")}
            return

        if _should_auto_compact(
            messages, params.model_config.context_window, params.model_config.max_output_tokens
        ):
            try:
                compacted, old_tokens, new_tokens = await _perform_compaction(messages, params)
                messages[:] = compacted
                yield {"type": "compact", "old_tokens": old_tokens, "new_tokens": new_tokens}
            except Exception as exc:
                async for hook_event in _run_on_error_hooks(
                    target="compact",
                    source="compact",
                    error_value=exc,
                ):
                    yield hook_event
                yield {"type": "error", "error": Exception(f"Auto-compact failed: {exc}")}

        _micro_compact_messages(messages)

        tool_uses: list[ToolUseBlock] = []
        assistant_content: list[ContentBlock] = []
        stop_reason = "end_turn"

        try:
            async for event in call_model(
                messages=messages,
                tools=params.tools,
                model_config=params.model_config,
                system_prompt_blocks=params.system_prompt_blocks,
                api_key=params.api_key_override or params.api_key,
                api_base_url=params.api_base_url,
                enable_thinking=params.enable_thinking,
                thinking_budget=params.thinking_budget,
                abort_signal=params.abort_signal,
            ):
                yield event
                if event["type"] == "tool_use":
                    tool_uses.append(event["tool_use"])
                elif event["type"] == "assistant_message":
                    assistant_content = event["message"].content
                elif event["type"] == "turn_complete":
                    stop_reason = event["stop_reason"]
        except PromptTooLongError:
            async for hook_event in _run_on_error_hooks(
                target="model",
                source="model",
                error_value="prompt_too_long",
            ):
                yield hook_event
            ptl_retries += 1
            if ptl_retries >= MAX_PTL_RETRIES:
                yield {
                    "type": "error",
                    "error": Exception(
                        "Prompt too long after "
                        f"{MAX_PTL_RETRIES} recovery attempts. "
                        "Use /compact and retry."
                    ),
                }
                return
            messages[:] = _truncate_for_ptl(messages)
            yield {
                "type": "error",
                "error": Exception(
                    "Prompt too long, truncating old turns "
                    f"(attempt {ptl_retries}/{MAX_PTL_RETRIES})."
                ),
            }
            continue
        except Exception as exc:
            classified = classify_error(exc)
            async for hook_event in _run_on_error_hooks(
                target="model",
                source="model",
                error_value=classified,
            ):
                yield hook_event
            yield {"type": "error", "error": classified}
            return

        ptl_retries = 0
        if assistant_content:
            messages.append(_assistant_message(assistant_content))

        if not tool_uses:
            yield {"type": "turn_complete", "stop_reason": stop_reason}
            return

        tool_results: list[tuple[str, ToolResult]] = []
        allowed_tools: list[ToolUseBlock] = []

        for tool_use in tool_uses:
            allowed, message = await _check_tool_permission(tool_use, params, tool_context)
            if allowed:
                allowed_tools.append(tool_use)
                continue

            denied = ToolResult(
                result=message or f"Permission denied for {tool_use.name}.", is_error=True
            )
            tool_results.append((tool_use.id, denied))
            yield {
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "tool_name": tool_use.name,
                "result": denied.result,
                "is_error": True,
            }

        if allowed_tools:
            async for event in execute_tools(allowed_tools, params.tools, tool_context):
                yield event
                if event["type"] == "tool_result":
                    tool_results.append(
                        (
                            event["tool_use_id"],
                            ToolResult(result=event["result"], is_error=event["is_error"]),
                        )
                    )

        ordered: list[tuple[str, ToolResult]] = []
        for tool_use in tool_uses:
            found = next((r for r in tool_results if r[0] == tool_use.id), None)
            ordered.append(
                found or (tool_use.id, ToolResult(result="Tool execution failed", is_error=True))
            )

        messages.append(_tool_result_message(ordered))
        if hook_prompt_appends:
            for prompt in hook_prompt_appends:
                messages.append(_hook_prompt_message(prompt))
            hook_prompt_appends.clear()

        turn_count += 1
        if turn_count >= params.max_turns:
            yield {"type": "max_turns_reached", "max_turns": params.max_turns}
            return


async def run_sub_agent(
    prompt: str,
    params: QueryParams,
    tools: list[str] | None = None,
    disallowed_tools: list[str] | None = None,
    max_turns: int | None = None,
    model: str | None = None,
) -> str:
    filtered_tools = params.tools
    if tools is not None:
        allow = set(tools)
        filtered_tools = [tool for tool in filtered_tools if tool.name in allow]
    if disallowed_tools is not None:
        deny = set(disallowed_tools)
        filtered_tools = [tool for tool in filtered_tools if tool.name not in deny]

    sub_messages = [
        Message(role="user", content=[TextBlock(type="text", text=prompt)], id=str(uuid.uuid4()))
    ]

    sub_params = QueryParams(
        messages=sub_messages,
        tools=filtered_tools,
        model_config=get_model_config(model) if model else params.model_config,
        system_prompt_blocks=params.system_prompt_blocks,
        permission_mode=params.permission_mode,
        api_key=params.api_key,
        cwd=params.cwd,
        session_id=params.session_id,
        on_permission_request=params.on_permission_request,
        read_file_state=params.read_file_state.clone(),
        file_history=params.file_history,
        max_turns=max_turns or params.max_turns,
        abort_signal=params.abort_signal,
        enable_thinking=params.enable_thinking,
        thinking_budget=params.thinking_budget,
        api_key_override=params.api_key_override,
        api_base_url=params.api_base_url,
    )

    chunks: list[str] = []
    async for event in agent_loop(sub_params):
        if event["type"] == "assistant_text":
            chunks.append(event["text"])
    params.read_file_state.merge(sub_params.read_file_state)
    return "".join(chunks).strip() or "(No response from sub-agent)"
