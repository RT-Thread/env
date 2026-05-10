"""Terminal formatting helpers."""

from __future__ import annotations


def _wrap(code: str, text: str) -> str:
    return f"\x1b[{code}m{text}\x1b[0m"


def blue(text: str) -> str:
    return _wrap("34", text)


def green(text: str) -> str:
    return _wrap("32", text)


def yellow(text: str) -> str:
    return _wrap("33", text)


def red(text: str) -> str:
    return _wrap("31", text)


def dim(text: str) -> str:
    return _wrap("2", text)


def bold(text: str) -> str:
    return _wrap("1", text)


def gold(text: str) -> str:
    return _wrap("33;1", text)
