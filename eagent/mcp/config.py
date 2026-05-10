"""MCP configuration loading from settings files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eagent.mcp.types import McpServerConfig
from eagent.paths import env_root

PROJECT_CONFIG_DIR = ".agents"
SETTINGS_FILE = "settings.json"


def _read_settings(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _extract_servers(settings: dict[str, Any] | None) -> dict[str, McpServerConfig]:
    if not settings:
        return {}
    mcp = settings.get("mcpServers")
    if not isinstance(mcp, dict):
        return {}

    out: dict[str, McpServerConfig] = {}
    for name, cfg in mcp.items():
        if not isinstance(cfg, dict):
            continue
        command = cfg.get("command")
        if not isinstance(command, str) or not command.strip():
            continue
        args = cfg.get("args")
        env = cfg.get("env")
        out[name] = McpServerConfig(
            command=command.strip(),
            args=[str(a) for a in args] if isinstance(args, list) else [],
            env={str(k): str(v) for k, v in env.items()} if isinstance(env, dict) else None,
        )
    return out


def resolve_mcp_command(config: McpServerConfig) -> McpServerConfig:
    command = config.command.strip()
    if command.startswith("~"):
        command = str(Path(command).expanduser())
    return McpServerConfig(command=command, args=list(config.args), env=dict(config.env or {}))


async def load_mcp_config(cwd: str) -> dict[str, McpServerConfig]:
    root = Path(cwd).resolve()

    user_servers: dict[str, McpServerConfig] = {}
    project_servers: dict[str, McpServerConfig] = {}

    user_settings = _read_settings(env_root() / SETTINGS_FILE)
    user_servers.update(_extract_servers(user_settings))

    project_settings = _read_settings(root / PROJECT_CONFIG_DIR / SETTINGS_FILE)
    project_servers.update(_extract_servers(project_settings))

    merged = {**user_servers, **project_servers}
    return {name: resolve_mcp_command(cfg) for name, cfg in merged.items()}


def get_mcp_config_paths(cwd: str) -> dict[str, str]:
    root = Path(cwd).resolve()
    return {
        "project": str(root / PROJECT_CONFIG_DIR / SETTINGS_FILE),
        "user": str(env_root() / SETTINGS_FILE),
    }
