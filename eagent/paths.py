"""Shared EnvAgent filesystem locations."""

from __future__ import annotations

import os
from pathlib import Path


def env_root() -> Path:
    configured = os.getenv("ENV_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".env").resolve()


def agents_root() -> Path:
    return (Path.home() / ".agents").resolve()


def project_agents_root(cwd: str) -> Path:
    return Path(cwd).expanduser().resolve() / ".agents"
