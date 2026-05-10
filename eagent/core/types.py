"""Shared runtime types for eagent."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypedDict

MessageRole = Literal["user", "assistant"]
PermissionMode = Literal["default", "plan", "acceptEdits", "bypassPermissions"]
PermissionBehavior = Literal["allow", "deny", "ask"]


@dataclass
class TextBlock:
    type: Literal["text"]
    text: str


@dataclass
class ToolUseBlock:
    type: Literal["tool_use"]
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResultBlock:
    type: Literal["tool_result"]
    tool_use_id: str
    content: str | list[ContentBlock]
    is_error: bool = False


@dataclass
class ThinkingBlock:
    type: Literal["thinking"]
    thinking: str


@dataclass
class RedactedThinkingBlock:
    type: Literal["redacted_thinking"]
    data: str


@dataclass
class ImageSource:
    type: Literal["base64"]
    media_type: str
    data: str


@dataclass
class ImageBlock:
    type: Literal["image"]
    source: ImageSource


ContentBlock = (
    TextBlock
    | ToolUseBlock
    | ToolResultBlock
    | ThinkingBlock
    | RedactedThinkingBlock
    | ImageBlock
)


@dataclass
class Message:
    role: MessageRole
    content: list[ContentBlock]
    id: str | None = None


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


@dataclass
class ToolResult:
    result: str
    is_error: bool = False


@dataclass
class PermissionDecision:
    behavior: PermissionBehavior
    message: str | None = None
    updated_input: dict[str, Any] | None = None


@dataclass
class FileState:
    content: str
    timestamp: float
    offset: int | None = None
    limit: int | None = None
    is_partial_view: bool = False


class FileStateCache(Protocol):
    def get(self, path: str) -> FileState | None: ...

    def set(self, path: str, state: FileState) -> None: ...

    def has(self, path: str) -> bool: ...

    def delete(self, path: str) -> None: ...

    def keys(self) -> Iterable[str]: ...

    def clone(self) -> FileStateCache: ...

    def merge(self, other: FileStateCache) -> None: ...

    @property
    def size(self) -> int: ...


@dataclass
class FileHistoryBackup:
    backup_file_name: str | None
    version: int
    backup_time: float


@dataclass
class FileHistorySnapshot:
    message_id: str
    tracked_file_backups: dict[str, FileHistoryBackup] = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class FileHistoryState:
    snapshots: list[FileHistorySnapshot] = field(default_factory=list)
    tracked_files: set[str] = field(default_factory=set)
    snapshot_sequence: int = 0


@dataclass
class ToolContext:
    cwd: str
    read_file_state: FileStateCache
    file_history: FileHistoryState
    modified_files: set[str]
    session_id: str
    permission_mode: PermissionMode
    on_permission_request: Callable[[str, Any, str], Awaitable[PermissionDecision]]
    abort_signal: Any | None = None
    hook_runtime: Any | None = None
    on_hook_prompt_append: Callable[[str], None] | None = None
    dev_mode: bool = False


class ToolDef(Protocol):
    name: str
    description: str | Callable[[dict[str, Any] | None], str]
    input_schema: dict[str, Any]

    async def call(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult: ...

    def prompt(self) -> str: ...

    def is_concurrency_safe(self, input_data: dict[str, Any]) -> bool: ...

    def is_read_only(self, input_data: dict[str, Any]) -> bool: ...

    def user_facing_name(self, input_data: dict[str, Any]) -> str: ...


@dataclass
class Tool:
    name: str
    description: str | Callable[[dict[str, Any] | None], str]
    input_schema: dict[str, Any]
    call: Callable[[dict[str, Any], ToolContext], Awaitable[ToolResult]]
    prompt: Callable[[], str] = lambda: ""
    is_concurrency_safe: Callable[[dict[str, Any]], bool] = lambda _i: False
    is_read_only: Callable[[dict[str, Any]], bool] = lambda _i: False
    max_result_size_chars: int = 30_000
    user_facing_name: Callable[[dict[str, Any]], str] = lambda _i: ""


@dataclass
class PermissionRule:
    tool: str
    behavior: Literal["allow", "deny"]
    source: Literal["session", "project", "user"]
    content: str | None = None


@dataclass
class ModelConfig:
    model: str
    context_window: int
    max_output_tokens: int
    supports_thinking: bool
    supports_caching: bool
    price_per_input_token: float
    price_per_output_token: float
    price_per_cache_read: float
    price_per_cache_write: float


@dataclass
class SystemPromptBlock:
    type: Literal["text"]
    text: str
    cache_control: dict[str, str] | None = None


@dataclass
class QueryParams:
    messages: list[Message]
    tools: list[Tool]
    model_config: ModelConfig
    system_prompt_blocks: list[SystemPromptBlock]
    permission_mode: PermissionMode
    api_key: str
    cwd: str
    session_id: str
    on_permission_request: Callable[[str, Any, str], Awaitable[PermissionDecision]]
    read_file_state: FileStateCache
    file_history: FileHistoryState
    max_turns: int = 200
    abort_signal: Any | None = None
    enable_thinking: bool = False
    thinking_budget: int | None = None
    api_key_override: str | None = None
    api_base_url: str | None = None
    hook_runtime: Any | None = None
    dev_mode: bool = False


@dataclass
class CostTracker:
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0
    turns: int = 0

    def add(self, usage: TokenUsage) -> None:
        self.total_input_tokens += int(usage.input_tokens or 0)
        self.total_output_tokens += int(usage.output_tokens or 0)
        self.total_cache_read_tokens += int(usage.cache_read_tokens or 0)
        self.total_cache_creation_tokens += int(usage.cache_creation_tokens or 0)
        self.turns += 1

    def total_cost_usd(self, config: ModelConfig) -> float:
        return (
            self.total_input_tokens * config.price_per_input_token
            + self.total_output_tokens * config.price_per_output_token
            + self.total_cache_read_tokens * config.price_per_cache_read
            + self.total_cache_creation_tokens * config.price_per_cache_write
        )


class StreamEvent(TypedDict, total=False):
    type: Literal[
        "assistant_text",
        "assistant_message",
        "tool_use",
        "tool_result",
        "tool_start",
        "turn_complete",
        "usage",
        "compact",
        "error",
        "max_turns_reached",
        "thinking",
        "hook_debug",
    ]
    text: str
    message: Message
    tool_use: ToolUseBlock
    tool_use_id: str
    tool_name: str
    result: str
    is_error: bool
    input: dict[str, Any]
    stop_reason: str
    usage: TokenUsage
    old_tokens: int
    new_tokens: int
    error: Exception
    max_turns: int


@dataclass
class CommandContext:
    messages: list[Message]
    tools: list[Tool]
    model_config: ModelConfig
    cwd: str
    session_id: str
    cost_tracker: CostTracker
    file_history: FileHistoryState
    read_file_state: FileStateCache
    permission_mode: PermissionMode
    set_permission_mode: Callable[[PermissionMode], None]
    set_model: Callable[[str], str]
    clear_messages: Callable[[], None]
    compact: Callable[[], Awaitable[None]]
    resume_session: Callable[[str], Awaitable[str | None]]
    send_prompt: Callable[[str], None]
    set_input_draft: Callable[[str], None] | None = None
    interactive: bool = False
    new_session: Callable[[], Awaitable[str]] | None = None
    dev_mode: bool = False


class SlashCommand(Protocol):
    name: str
    description: str

    async def execute(self, args: str, context: CommandContext) -> str | None: ...
