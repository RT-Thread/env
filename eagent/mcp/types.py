"""Types for MCP subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class McpServerConfig:
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None


@dataclass
class JsonRpcRequest:
    jsonrpc: str
    id: int
    method: str
    params: dict[str, Any]


@dataclass
class JsonRpcError:
    code: int
    message: str
    data: Any | None = None


@dataclass
class JsonRpcResponse:
    jsonrpc: str
    id: int | None = None
    result: Any | None = None
    error: JsonRpcError | None = None


@dataclass
class McpToolDefinition:
    name: str
    description: str | None = None
    inputSchema: dict[str, Any] | None = None


@dataclass
class McpToolCallResult:
    content: list[dict[str, Any]]
    isError: bool = False
