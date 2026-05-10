"""Load project/user AI context markdown files."""

from __future__ import annotations

from pathlib import Path

from eagent.paths import env_root

CONTEXT_FILES = [
    "tasks.md",
    "requirements.md",
    "requirements",
    "design.md",
    "ENV_AGENT.md",
    "ENV_AGENT.local.md",
]
LEGACY_PROJECT_FILES = [
    "ENV_AGENT.md",
    "ENV_AGENT.local.md",
]


def _try_read(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
        return text.strip() if text.strip() else None
    except Exception:
        return None


async def load_agent_memory(cwd: str) -> str:
    base = Path(cwd).resolve()
    fragments: list[str] = []
    seen_sources: set[Path] = set()

    source_paths: list[Path] = []
    source_paths.extend(base / ".agents" / rel for rel in CONTEXT_FILES)
    source_paths.extend(base / rel for rel in LEGACY_PROJECT_FILES)
    source_paths.extend(env_root() / rel for rel in CONTEXT_FILES)

    for p in source_paths:
        resolved = p.resolve()
        if resolved in seen_sources:
            continue
        content = _try_read(p)
        if content:
            seen_sources.add(resolved)
            source = str(p.relative_to(base)) if p.is_relative_to(base) else str(p)
            fragments.append(f"# Source: {source}\n\n{content}")

    return "\n\n---\n\n".join(fragments)


async def has_agent_memory(cwd: str) -> bool:
    return bool(await load_agent_memory(cwd))
