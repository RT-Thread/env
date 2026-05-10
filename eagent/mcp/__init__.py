"""MCP subsystem."""

from eagent.mcp.client import McpClient, create_mcp_client
from eagent.mcp.config import get_mcp_config_paths, load_mcp_config, resolve_mcp_command
from eagent.mcp.manager import (
    get_active_mcp_server_count,
    get_active_mcp_server_names,
    initialize_mcp_servers,
    shutdown_mcp_servers,
)
from eagent.mcp.types import McpServerConfig, McpToolCallResult, McpToolDefinition

__all__ = [
    "McpClient",
    "create_mcp_client",
    "McpServerConfig",
    "McpToolDefinition",
    "McpToolCallResult",
    "load_mcp_config",
    "resolve_mcp_command",
    "get_mcp_config_paths",
    "initialize_mcp_servers",
    "shutdown_mcp_servers",
    "get_active_mcp_server_count",
    "get_active_mcp_server_names",
]
