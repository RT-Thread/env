"""MCP manager for initializing servers and wrapping tools."""

from __future__ import annotations

import asyncio

from eagent.core.types import Tool
from eagent.mcp.client import McpClient, create_mcp_client
from eagent.mcp.config import load_mcp_config
from eagent.tools.mcp_wrapper import wrap_mcp_tool

_active_clients: list[McpClient] = []


async def initialize_mcp_servers(cwd: str) -> list[Tool]:
    configs = await load_mcp_config(cwd)
    if not configs:
        return []

    async def _connect(name: str, config) -> tuple[str, list[Tool]]:
        client = create_mcp_client(name, config)
        try:
            await client.connect()
            _active_clients.append(client)
            tool_defs = await client.list_tools()
            wrapped = [
                wrap_mcp_tool(
                    server_name=name,
                    tool_name=tool_def.name,
                    description=tool_def.description or f"MCP tool: {tool_def.name}",
                    input_schema=tool_def.inputSchema or {"type": "object"},
                    client=client,
                )
                for tool_def in tool_defs
            ]
            return name, wrapped
        except Exception as exc:
            print(f"[mcp] Failed to connect to server '{name}': {exc}")
            try:
                await client.disconnect()
            except Exception:
                pass
            return name, []

    tasks = [_connect(name, cfg) for name, cfg in configs.items()]
    results = await asyncio.gather(*tasks)

    tools: list[Tool] = []
    for name, server_tools in results:
        if server_tools:
            print(f"[mcp] Server '{name}': {len(server_tools)} tool(s) registered")
            tools.extend(server_tools)
    return tools


async def shutdown_mcp_servers() -> None:
    await asyncio.gather(
        *(client.disconnect() for client in list(_active_clients)), return_exceptions=True
    )
    _active_clients.clear()


def get_active_mcp_server_count() -> int:
    return sum(1 for client in _active_clients if client.is_connected)


def get_active_mcp_server_names() -> list[str]:
    return [client.server_name for client in _active_clients if client.is_connected]
