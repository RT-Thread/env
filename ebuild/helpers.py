# -*- coding: utf-8 -*-
"""Shared helpers for the build system."""

from __future__ import annotations

import os
from typing import Any, Dict, List


def normalize_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def split_flags(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        return [item for item in value.split() if item]
    return [str(value)]


def merge_flags(*values: Any) -> List[str]:
    flags: List[str] = []
    for value in values:
        flags.extend(split_flags(value))
    return flags


def normalize_defines(value: Any) -> Dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        defines: Dict[str, str] = {}
        for item in value:
            if not item:
                continue
            text = str(item)
            if '=' in text:
                key, val = text.split('=', 1)
                defines[key] = val
            else:
                defines[text] = '1'
        return defines
    text = str(value)
    if '=' in text:
        key, val = text.split('=', 1)
        return {key: val}
    return {text: '1'}


def defines_to_list(defines: Dict[str, str]) -> List[str]:
    items = []
    for key, val in defines.items():
        if val == '1':
            items.append(key)
        else:
            items.append(f"{key}={val}")
    return items


def source_to_path(source: Any) -> str:
    if hasattr(source, 'rfile'):
        return source.rfile().abspath
    if hasattr(source, 'abspath'):
        return source.abspath
    return str(source)
