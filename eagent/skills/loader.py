"""Skill loader and frontmatter parser."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

from eagent.paths import agents_root, env_root
from eagent.skills.types import SkillDefinition, SkillLoadResult, SkillSource

SKILL_FILE = "SKILL.md"


def _parse_simple_yaml(yaml_text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    lines = yaml_text.splitlines()
    current_key: str | None = None
    current_array: list[str] | None = None

    for raw in lines:
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        array_match = re.match(r"^\s*-\s+(.+)\s*$", line)
        if array_match and current_key:
            if current_array is None:
                current_array = []
            current_array.append(_unquote(array_match.group(1).strip()))
            result[current_key] = current_array
            continue

        if current_array is not None and current_key:
            result[current_key] = current_array
            current_array = None

        kv = re.match(r"^([a-zA-Z0-9_-]+)\s*:\s*(.*)$", line)
        if not kv:
            continue

        current_key = kv.group(1)
        value = kv.group(2).strip()

        if not value:
            current_array = []
            continue

        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1]
            result[current_key] = [
                _unquote(part.strip()) for part in inner.split(",") if part.strip()
            ]
            current_array = None
            continue

        lower = value.lower()
        if lower in {"true", "yes"}:
            result[current_key] = True
            current_array = None
            continue
        if lower in {"false", "no"}:
            result[current_key] = False
            current_array = None
            continue
        if re.fullmatch(r"-?\d+(\.\d+)?", value):
            result[current_key] = float(value) if "." in value else int(value)
            current_array = None
            continue

        result[current_key] = _unquote(value)
        current_array = None

    if current_array is not None and current_key:
        result[current_key] = current_array

    return result


def _unquote(value: str) -> str:
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    stripped = content.lstrip()
    if not stripped.startswith("---"):
        return {}, content

    rest = stripped[3:]
    idx = rest.find("\n---")
    if idx < 0:
        return {}, content

    yaml = rest[:idx].strip()
    body = rest[idx + 4 :].lstrip("\n")
    return _parse_simple_yaml(yaml), body


def _normalize_string_list(value: Any) -> list[str] | None:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        items = [str(v) for v in value if isinstance(v, (str, int, float))]
        return items if items else None
    return None


def _split_args(args: str) -> list[str]:
    if not args.strip():
        return []

    values: list[str] = []
    current: list[str] = []
    in_quote = False
    quote_char = ""
    i = 0
    while i < len(args):
        ch = args[i]
        if ch in {"'", '"'}:
            if in_quote and ch == quote_char:
                in_quote = False
                quote_char = ""
                i += 1
                continue
            if not in_quote:
                in_quote = True
                quote_char = ch
                i += 1
                continue
        if not in_quote and ch.isspace():
            if current:
                values.append("".join(current))
                current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    if current:
        values.append("".join(current))
    return values


def _escape_regex(text: str) -> str:
    return re.escape(text)


def _make_expander(template: str, skill_root: str, arg_names: list[str] | None):
    async def _expand(args: str) -> str:
        result = template

        for key in (
            "${ENV_AGENT_SKILL_DIR}",
            "$ENV_AGENT_SKILL_DIR",
        ):
            result = result.replace(key, skill_root)

        result = result.replace("$ARGUMENTS", args)
        positional = _split_args(args)

        if arg_names:
            for idx, name in enumerate(arg_names):
                value = positional[idx] if idx < len(positional) else ""
                result = re.sub(rf"\\${_escape_regex(name)}\\b", value, result)

        for i in range(1, 10):
            value = positional[i - 1] if i - 1 < len(positional) else ""
            result = re.sub(rf"\\${i}\\b", value, result)

        return result

    return _expand


def _matches_paths(skill: SkillDefinition, cwd: Path) -> bool:
    if not skill.paths:
        return True
    for pattern in skill.paths:
        if any(fnmatch.fnmatch(str(path.relative_to(cwd)), pattern) for path in cwd.rglob("*")):
            return True
    return False


async def parse_skill_file(file_path: str) -> SkillDefinition | None:
    path = Path(file_path)
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return None
    if not content.strip():
        return None

    frontmatter, body = parse_frontmatter(content)

    skill_root = str(path.parent.resolve())
    name = str(frontmatter.get("name") or path.parent.name)
    description = str(frontmatter.get("description") or f"Skill: {name}")
    argument_names = _normalize_string_list(frontmatter.get("arguments"))
    paths = _normalize_string_list(frontmatter.get("paths"))
    allowed_tools = _normalize_string_list(frontmatter.get("allowed-tools"))

    skill = SkillDefinition(
        name=name,
        description=description,
        when_to_use=str(frontmatter.get("when_to_use")) if frontmatter.get("when_to_use") else None,
        argument_hint=(
            str(frontmatter.get("argument-hint")) if frontmatter.get("argument-hint") else None
        ),
        argument_names=argument_names,
        allowed_tools=allowed_tools,
        model=str(frontmatter.get("model")) if frontmatter.get("model") else None,
        user_invocable=bool(frontmatter.get("user-invocable", True)),
        context="fork" if str(frontmatter.get("context") or "inline") == "fork" else "inline",
        agent=str(frontmatter.get("agent")) if frontmatter.get("agent") else None,
        paths=paths,
        skill_root=skill_root,
        get_prompt=_make_expander(body, skill_root, argument_names),
    )

    return skill


async def load_skills_from_dir(skills_dir: str, source: SkillSource) -> list[SkillLoadResult]:
    root = Path(skills_dir)
    if not root.exists() or not root.is_dir():
        return []

    results: list[SkillLoadResult] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        skill_file = child / SKILL_FILE
        if not skill_file.exists():
            continue
        skill = await parse_skill_file(str(skill_file))
        if skill is None:
            continue
        results.append(SkillLoadResult(skill=skill, source=source, file_path=str(skill_file)))
    return results


async def load_all_skills(cwd: str) -> list[SkillDefinition]:
    cwd_root = Path(cwd).resolve()
    seen: dict[str, SkillLoadResult] = {}

    search_dirs: list[tuple[Path, SkillSource]] = [
        (cwd_root / ".agents" / "skills", "project"),
        (agents_root() / "skills", "user"),
        (env_root() / "skills", "user"),
    ]

    for skills_dir, source in search_dirs:
        results = await load_skills_from_dir(str(skills_dir), source)
        for result in results:
            key = result.skill.name.lower()
            if key not in seen:
                seen[key] = result

    out: list[SkillDefinition] = []
    for item in seen.values():
        if _matches_paths(item.skill, cwd_root):
            out.append(item.skill)
    return out
