"""MCP stdio JSON-RPC client."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import suppress
from typing import Any

from eagent.mcp.types import (
    JsonRpcError,
    JsonRpcResponse,
    McpServerConfig,
    McpToolDefinition,
)

MCP_PROTOCOL_VERSION = "2024-11-05"
MAX_RECONNECT_RETRIES = 3
REQUEST_TIMEOUT_SECONDS = 60
INIT_TIMEOUT_SECONDS = 30


class McpClient:
    def __init__(
        self,
        server_name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.server_name = server_name
        self.command = command
        self.args = args or []
        self.env = env or {}

        self.process: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._next_id = 1
        self._connected = False
        self._reconnect_count = 0
        self._pending: dict[int, asyncio.Future[JsonRpcResponse]] = {}

    @property
    def is_connected(self) -> bool:
        return self._connected and self.process is not None and self.process.returncode is None

    async def connect(self) -> None:
        if self.is_connected:
            return
        await self._spawn_process()
        await self._initialize()
        self._connected = True
        self._reconnect_count = 0

    async def list_tools(self) -> list[McpToolDefinition]:
        await self._ensure_connected()
        response = await self._send_request("tools/list", {})
        if response.error:
            raise RuntimeError(
                f'MCP tools/list error from "{self.server_name}": {response.error.message}'
            )
        result = response.result if isinstance(response.result, dict) else {}
        tools_raw = result.get("tools", []) if isinstance(result, dict) else []
        tools: list[McpToolDefinition] = []
        if isinstance(tools_raw, list):
            for tool in tools_raw:
                if not isinstance(tool, dict):
                    continue
                tools.append(
                    McpToolDefinition(
                        name=str(tool.get("name", "")),
                        description=(
                            str(tool.get("description"))
                            if tool.get("description") is not None
                            else None
                        ),
                        inputSchema=(
                            tool.get("inputSchema")
                            if isinstance(tool.get("inputSchema"), dict)
                            else None
                        ),
                    )
                )
        return tools

    async def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_connected()
        response = await self._send_request("tools/call", {"name": name, "arguments": args})
        if response.error:
            return {
                "content": [{"type": "text", "text": response.error.message}],
                "isError": True,
            }
        result = response.result if isinstance(response.result, dict) else None
        if not result:
            return {"content": [{"type": "text", "text": "(empty result)"}], "isError": False}
        return result

    async def disconnect(self) -> None:
        self._connected = False

        for req_id, future in list(self._pending.items()):
            if not future.done():
                future.set_exception(RuntimeError("MCP client disconnecting"))
            self._pending.pop(req_id, None)

        if self._reader_task:
            self._reader_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None

        if self._stderr_task:
            self._stderr_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._stderr_task
            self._stderr_task = None

        if self.process:
            if self.process.stdin is not None:
                self.process.stdin.close()
            if self.process.returncode is None:
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2)
                except TimeoutError:
                    self.process.kill()
                    await self.process.wait()
            self.process = None

    async def _spawn_process(self) -> None:
        env = {**os.environ, **self.env}
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        self._reader_task = asyncio.create_task(self._reader_loop())
        self._stderr_task = asyncio.create_task(self._stderr_loop())

    async def _stderr_loop(self) -> None:
        if self.process is None or self.process.stderr is None:
            return
        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    return
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    print(f"[mcp:{self.server_name}] {text}")
        except asyncio.CancelledError:
            return

    async def _reader_loop(self) -> None:
        if self.process is None or self.process.stdout is None:
            return

        while True:
            line = await self.process.stdout.readline()
            if not line:
                await self._handle_process_exit()
                return

            payload = line.decode("utf-8", errors="replace").strip()
            if not payload:
                continue

            try:
                message = json.loads(payload)
            except json.JSONDecodeError:
                continue

            msg_id = message.get("id")
            if isinstance(msg_id, int) and msg_id in self._pending:
                future = self._pending.pop(msg_id)
                if future.done():
                    continue

                error = message.get("error")
                response = JsonRpcResponse(
                    jsonrpc=str(message.get("jsonrpc", "2.0")),
                    id=msg_id,
                    result=message.get("result"),
                    error=(
                        JsonRpcError(**error)
                        if isinstance(error, dict) and "message" in error
                        else None
                    ),
                )
                future.set_result(response)

    async def _initialize(self) -> None:
        response = await self._send_request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "RTE-AI", "version": "0.1.0"},
            },
            timeout=INIT_TIMEOUT_SECONDS,
        )
        if response.error:
            raise RuntimeError(
                f'MCP initialize failed for "{self.server_name}": {response.error.message}'
            )
        await self._send_notification("notifications/initialized", {})

    async def _send_request(
        self,
        method: str,
        params: dict[str, Any],
        timeout: int = REQUEST_TIMEOUT_SECONDS,
    ) -> JsonRpcResponse:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError(f'MCP server "{self.server_name}" stdin not available')

        req_id = self._next_id
        self._next_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        loop = asyncio.get_running_loop()
        future: asyncio.Future[JsonRpcResponse] = loop.create_future()
        self._pending[req_id] = future

        self.process.stdin.write((json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"))
        await self.process.stdin.drain()

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError as exc:
            self._pending.pop(req_id, None)
            raise RuntimeError(
                f'MCP request "{method}" to "{self.server_name}" timed out after {timeout}s'
            ) from exc

    async def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        if self.process is None or self.process.stdin is None:
            return
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        self.process.stdin.write((json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"))
        await self.process.stdin.drain()

    async def _ensure_connected(self) -> None:
        if self.is_connected:
            return
        await self._attempt_reconnect()

    async def _attempt_reconnect(self) -> None:
        if self._reconnect_count >= MAX_RECONNECT_RETRIES:
            raise RuntimeError(f'MCP server "{self.server_name}" reconnect retries exhausted')
        self._reconnect_count += 1
        await self.disconnect()
        await self.connect()

    async def _handle_process_exit(self) -> None:
        self._connected = False
        if self.process is not None:
            await self.process.wait()

        for req_id, future in list(self._pending.items()):
            if not future.done():
                future.set_exception(RuntimeError(f'MCP server "{self.server_name}" exited'))
            self._pending.pop(req_id, None)


def create_mcp_client(server_name: str, config: McpServerConfig) -> McpClient:
    return McpClient(server_name, config.command, config.args, config.env)
