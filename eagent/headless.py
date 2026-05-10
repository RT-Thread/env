"""Headless SDK interface for eagent."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import Any

from eagent.context.git_context import get_git_context
from eagent.context.memory import load_agent_memory
from eagent.core.agent_loop import agent_loop
from eagent.core.api_client import get_model_config
from eagent.core.types import (
    Message,
    PermissionDecision,
    PermissionMode,
    QueryParams,
    StreamEvent,
    TextBlock,
    Tool,
)
from eagent.files.cache import create_file_state_cache
from eagent.files.history import create_file_history_state
from eagent.hooks import HookRuntime
from eagent.mcp.manager import initialize_mcp_servers
from eagent.prompt.system_prompt import build_system_prompt_blocks
from eagent.skills.skill_tool import set_skill_query_params
from eagent.tools.agent_tool import set_agent_query_params
from eagent.tools.registry import initialize_tools, register_dynamic_tools
from eagent.utils.cost import create_cost_tracker, summarize_cost


@dataclass
class AgentOptions:
    api_key: str
    model: str = "sonnet"
    cwd: str = "."
    max_turns: int = 200
    permission_mode: PermissionMode = "bypassPermissions"
    enable_thinking: bool = False
    thinking_budget: int | None = None
    tools: list[Tool] | None = None
    on_permission_request: Callable[[str, Any, str], Any] | None = None
    enable_mcp: bool = False


class AgentInstance:
    def __init__(self, options: AgentOptions) -> None:
        self.options = options
        self.cwd = options.cwd
        self.model_config = get_model_config(options.model)
        self.session_id = str(uuid.uuid4())
        self.cost_tracker = create_cost_tracker()
        self.read_file_state = create_file_state_cache()
        self.file_history = create_file_history_state()
        self.messages: list[Message] = []
        self.system_prompt_blocks = []
        self.tools: list[Tool] = []
        self.hook_runtime = HookRuntime(self.cwd)
        self._session_hooks_ran = False
        self._session_end_hooks_ran = False

    def _append_user_message(self, text: str) -> None:
        self.messages.append(
            Message(role="user", content=[TextBlock(type="text", text=text)], id=str(uuid.uuid4()))
        )

    def _last_assistant_message(self) -> str:
        for message in reversed(self.messages):
            if message.role != "assistant":
                continue
            chunks: list[str] = []
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text.strip()
                    if text:
                        chunks.append(text)
            if chunks:
                return "\n".join(chunks).strip()
        return ""

    async def initialize(self) -> None:
        agent_memory = await load_agent_memory(self.cwd)
        git_context = await get_git_context(self.cwd)
        self.system_prompt_blocks = build_system_prompt_blocks(
            agent_memory, git_context, self.cwd, self.model_config.model
        )

        self.tools = self.options.tools or await initialize_tools(self.cwd)
        if self.options.enable_mcp:
            mcp_tools = await initialize_mcp_servers(self.cwd)
            if mcp_tools:
                register_dynamic_tools(mcp_tools)
                self.tools.extend(mcp_tools)

    async def query(self, prompt: str) -> AsyncGenerator[StreamEvent, None]:
        if not self._session_hooks_ran:
            self._session_hooks_ran = True
            session_outcome = await self.hook_runtime.run(
                "session_start",
                target=self.session_id,
                variables={"session_id": self.session_id, "cwd": self.cwd},
                cwd=self.cwd,
                dev_mode=False,
            )
            if session_outcome.aborted:
                yield {
                    "type": "error",
                    "error": Exception(
                        session_outcome.abort_reason or "Session start hook aborted."
                    ),
                }
                return
            for extra_prompt in session_outcome.prompt_appends:
                if extra_prompt.strip():
                    self._append_user_message(extra_prompt)

        prompt_text = prompt.strip()
        user_outcome = await self.hook_runtime.run(
            "user_prompt_submit",
            target=prompt_text if prompt_text else "(empty)",
            variables={"prompt": prompt, "prompt_text": prompt_text, "cwd": self.cwd},
            cwd=self.cwd,
            dev_mode=False,
        )
        if user_outcome.aborted:
            yield {
                "type": "error",
                "error": Exception(user_outcome.abort_reason or "User prompt hook aborted."),
            }
            return
        for extra_prompt in user_outcome.prompt_appends:
            if extra_prompt.strip():
                self._append_user_message(extra_prompt)

        self._append_user_message(prompt)

        async def _default_permission_handler(
            _tool: str, _input: Any, _message: str
        ) -> PermissionDecision:
            return PermissionDecision(behavior="allow")

        on_permission_request = self.options.on_permission_request or _default_permission_handler

        params = QueryParams(
            messages=self.messages,
            tools=self.tools,
            model_config=self.model_config,
            system_prompt_blocks=self.system_prompt_blocks,
            max_turns=self.options.max_turns,
            permission_mode=self.options.permission_mode,
            api_key=self.options.api_key,
            cwd=self.cwd,
            session_id=self.session_id,
            on_permission_request=on_permission_request,
            enable_thinking=self.options.enable_thinking,
            thinking_budget=self.options.thinking_budget,
            read_file_state=self.read_file_state,
            file_history=self.file_history,
            hook_runtime=self.hook_runtime,
            dev_mode=False,
        )

        set_agent_query_params(params)
        set_skill_query_params(params)

        stop_target = "turn_complete"
        stop_error = ""
        async for event in agent_loop(params):
            if event["type"] == "usage":
                self.cost_tracker.add(event["usage"])
            if event["type"] == "turn_complete":
                stop_target = str(event.get("stop_reason") or "turn_complete")
            elif event["type"] == "max_turns_reached":
                stop_target = f"max_turns:{event.get('max_turns')}"
            elif event["type"] == "error":
                stop_target = "error"
                stop_error = str(event.get("error") or "")
            yield event

        stop_outcome = await self.hook_runtime.run(
            "stop",
            target=stop_target,
            variables={
                "stop_reason": stop_target,
                "error": stop_error,
                "cwd": self.cwd,
                "last_assistant_message": self._last_assistant_message(),
            },
            cwd=self.cwd,
            dev_mode=False,
        )
        if stop_outcome.aborted:
            yield {
                "type": "error",
                "error": Exception(stop_outcome.abort_reason or "Stop hook aborted."),
            }
            return
        for extra_prompt in stop_outcome.prompt_appends:
            if extra_prompt.strip():
                self._append_user_message(extra_prompt)

        return

    def get_messages(self) -> list[Message]:
        return list(self.messages)

    def get_cost_summary(self) -> str:
        return summarize_cost(self.cost_tracker, self.model_config)

    def get_session_id(self) -> str:
        return self.session_id

    def reset(self) -> None:
        self.messages = []
        self._session_hooks_ran = False
        self._session_end_hooks_ran = False

    async def close(self) -> None:
        if self._session_end_hooks_ran:
            return
        self._session_end_hooks_ran = True
        await self.hook_runtime.run(
            "session_end",
            target=self.session_id,
            variables={"session_id": self.session_id, "cwd": self.cwd},
            cwd=self.cwd,
            dev_mode=False,
            allow_prompt_append=False,
        )


async def create_agent(options: AgentOptions) -> AgentInstance:
    agent = AgentInstance(options)
    await agent.initialize()
    return agent


async def one_shot(prompt: str, options: AgentOptions) -> dict[str, Any]:
    agent = await create_agent(options)
    text_parts: list[str] = []
    try:
        async for event in agent.query(prompt):
            if event["type"] == "assistant_text":
                text_parts.append(event["text"])
        return {"text": "".join(text_parts), "messages": agent.get_messages()}
    finally:
        await agent.close()
