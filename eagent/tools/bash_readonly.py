"""Read-only shell command analyzer used by Bash tool and permissions."""

from __future__ import annotations

import re
import shlex

SAFE_COMMANDS = {
    "cat",
    "head",
    "tail",
    "less",
    "more",
    "wc",
    "sort",
    "uniq",
    "diff",
    "comm",
    "find",
    "ls",
    "tree",
    "pwd",
    "echo",
    "printf",
    "grep",
    "egrep",
    "fgrep",
    "rg",
    "ag",
    "ack",
    "awk",
    "sed",
    "tr",
    "cut",
    "paste",
    "column",
    "fold",
    "fmt",
    "expand",
    "unexpand",
    "tee",
    "git",
    "which",
    "type",
    "file",
    "stat",
    "du",
    "df",
    "env",
    "printenv",
    "date",
    "uname",
    "whoami",
    "id",
    "hostname",
    "test",
    "true",
    "false",
    "npm",
    "yarn",
    "pnpm",
    "pip",
    "pip3",
    "realpath",
    "dirname",
    "basename",
    "readlink",
    "md5sum",
    "sha256sum",
    "sha1sum",
    "shasum",
    "xxd",
    "od",
    "strings",
    "nm",
    "hexdump",
    "jq",
    "xargs",
    "python",
    "python3",
    "node",
    "go",
    "rustc",
    "cargo",
    "java",
    "javac",
    "gcc",
    "clang",
}

GIT_SAFE_SUBCOMMANDS = {
    "log",
    "diff",
    "show",
    "status",
    "branch",
    "remote",
    "tag",
    "rev-parse",
    "rev-list",
    "describe",
    "shortlog",
    "blame",
    "ls-files",
    "ls-tree",
    "ls-remote",
    "cat-file",
    "name-rev",
    "config",
    "for-each-ref",
    "count-objects",
    "stash",
}

SAFE_NPM_SUBCOMMANDS = {
    "list",
    "ls",
    "view",
    "info",
    "show",
    "search",
    "outdated",
    "explain",
    "why",
    "fund",
    "audit",
    "doctor",
    "config",
}
SAFE_YARN_SUBCOMMANDS = {"list", "info", "why", "outdated", "config"}
SAFE_PIP_SUBCOMMANDS = {"list", "show", "freeze", "check"}

DANGEROUS_PATTERNS = (
    re.compile(r"\$\("),
    re.compile(r"`[^`]*`"),
    re.compile(r"<\("),
    re.compile(r">\("),
    re.compile(r"(?<![12<])>(?!&\d|/dev/null)"),
    re.compile(r">>(?!/dev/null)"),
    re.compile(r"\beval\b"),
    re.compile(r"\bexec\b"),
    re.compile(r"\bsource\b"),
)


def parse_command_parts(command: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    i = 0

    while i < len(command):
        ch = command[i]
        if ch == "\\" and not in_single and i + 1 < len(command):
            current.append(ch)
            current.append(command[i + 1])
            i += 2
            continue

        if ch == "'" and not in_double:
            in_single = not in_single
            current.append(ch)
            i += 1
            continue

        if ch == '"' and not in_single:
            in_double = not in_double
            current.append(ch)
            i += 1
            continue

        if not in_single and not in_double:
            if command.startswith("&&", i) or command.startswith("||", i):
                if "".join(current).strip():
                    parts.append("".join(current).strip())
                current = []
                i += 2
                continue
            if ch in {";", "|"}:
                if "".join(current).strip():
                    parts.append("".join(current).strip())
                current = []
                i += 1
                continue

        current.append(ch)
        i += 1

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _extract_command_and_args(part: str) -> tuple[str, list[str]]:
    try:
        tokens = shlex.split(part, posix=True)
    except ValueError:
        return "", []
    if not tokens:
        return "", []

    idx = 0
    while idx < len(tokens) and "=" in tokens[idx] and not tokens[idx].startswith(("./", "/")):
        left, _right = tokens[idx].split("=", 1)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", left):
            idx += 1
            continue
        break

    if idx >= len(tokens):
        return "", []

    return tokens[idx], tokens[idx + 1 :]


def _is_safe_sed(args: list[str]) -> bool:
    for arg in args:
        if arg in {"-i", "--in-place"}:
            return False
        if arg.startswith("-i") and len(arg) > 2:
            return False
    return True


def _is_safe_git(args: list[str]) -> bool:
    if not args:
        return False
    sub = args[0]
    if sub == "stash":
        if len(args) == 1:
            return False
        return args[1] in {"list", "show"}
    return sub in GIT_SAFE_SUBCOMMANDS


def _is_safe_pkg(cmd: str, args: list[str]) -> bool:
    if not args:
        return False
    sub = args[0]
    if cmd in {"npm", "pnpm"}:
        return sub in SAFE_NPM_SUBCOMMANDS
    if cmd == "yarn":
        return sub in SAFE_YARN_SUBCOMMANDS
    if cmd in {"pip", "pip3"}:
        return sub in SAFE_PIP_SUBCOMMANDS
    return True


def _is_readonly_part(part: str) -> bool:
    cmd, args = _extract_command_and_args(part)
    if not cmd:
        return False

    if cmd not in SAFE_COMMANDS:
        return False

    if cmd == "git":
        return _is_safe_git(args)
    if cmd in {"npm", "pnpm", "yarn", "pip", "pip3"}:
        return _is_safe_pkg(cmd, args)
    if cmd == "sed":
        return _is_safe_sed(args)
    if cmd == "tee":
        return any(a == "/dev/null" for a in args) or not args
    return True


def is_read_only_command(command: str) -> bool:
    stripped = command.strip()
    if not stripped:
        return False
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(stripped):
            return False

    parts = parse_command_parts(stripped)
    if not parts:
        return False
    return all(_is_readonly_part(part) for part in parts)
