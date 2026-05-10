"""Reload argument handling for Env-integrated and standalone agent entrypoints."""

from __future__ import annotations

import json
import os
import sys

_RELOAD_ARGV_ENV = "EAGENT_RELOAD_ARGV"


class ReloadArgs:
    @staticmethod
    def remember(argv: list[str]) -> None:
        os.environ[_RELOAD_ARGV_ENV] = json.dumps(argv)

    @staticmethod
    def current() -> list[str]:
        raw = os.environ.get(_RELOAD_ARGV_ENV)
        if raw:
            try:
                value = json.loads(raw)
            except Exception:
                value = None
            if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
                return value
        return list(sys.argv)
