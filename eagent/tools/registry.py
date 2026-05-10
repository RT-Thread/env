"""Tool registry and initialization."""

from __future__ import annotations

from collections.abc import Callable

from eagent.core.types import Tool
from eagent.tools.agent_tool import build_agent_tool
from eagent.tools.ask import build_ask_tool
from eagent.tools.bash import build_bash_tool
from eagent.tools.edit import build_edit_tool
from eagent.tools.glob_tool import build_glob_tool
from eagent.tools.grep_tool import build_grep_tool
from eagent.tools.notebook_edit import build_notebook_edit_tool
from eagent.tools.plan_mode import build_enter_plan_mode_tool, build_exit_plan_mode_tool
from eagent.tools.read import build_read_tool
from eagent.tools.todo import build_todo_tool
from eagent.tools.web_fetch import build_web_fetch_tool
from eagent.tools.web_search import build_web_search_tool
from eagent.tools.write import build_write_tool

_registry: dict[str, Tool] = {}
_initialized = False


def build_tool(definition: Tool) -> Tool:
    return Tool(
        name=definition.name,
        description=definition.description,
        input_schema=definition.input_schema,
        call=definition.call,
        prompt=definition.prompt or (lambda: ""),
        is_concurrency_safe=definition.is_concurrency_safe or (lambda _i: False),
        is_read_only=definition.is_read_only or (lambda _i: False),
        max_result_size_chars=definition.max_result_size_chars or 30_000,
        user_facing_name=definition.user_facing_name or (lambda _i: definition.name),
    )


def register_tool(tool: Tool) -> None:
    _registry[tool.name] = build_tool(tool)


def get_all_tools() -> list[Tool]:
    return list(_registry.values())


def get_tool_by_name(name: str) -> Tool | None:
    return _registry.get(name)


def has_tool_by_name(name: str) -> bool:
    return name in _registry


def get_tool_count() -> int:
    return len(_registry)


async def initialize_tools(cwd: str | None = None) -> list[Tool]:
    global _initialized
    if _initialized and _registry:
        return get_all_tools()

    builders: list[Callable[[], Tool]] = [
        build_bash_tool,
        build_read_tool,
        build_edit_tool,
        build_write_tool,
        build_glob_tool,
        build_grep_tool,
        build_agent_tool,
        build_ask_tool,
        build_todo_tool,
        build_web_fetch_tool,
        build_web_search_tool,
        build_enter_plan_mode_tool,
        build_exit_plan_mode_tool,
        build_notebook_edit_tool,
    ]

    for factory in builders:
        register_tool(factory())

    # Optional skill tool.
    try:
        from eagent.skills.skill_tool import build_skill_tool, initialize_skills

        await initialize_skills(cwd or ".")
        register_tool(build_skill_tool())
    except Exception:
        pass

    _initialized = True
    return get_all_tools()


def register_dynamic_tools(tools: list[Tool]) -> None:
    for tool in tools:
        register_tool(tool)


def reset_registry() -> None:
    global _initialized
    _registry.clear()
    _initialized = False


def get_read_only_tool_names() -> list[str]:
    names: list[str] = []
    for tool in get_all_tools():
        try:
            if tool.is_read_only({}):
                names.append(tool.name)
        except Exception:
            continue
    return names


def filter_tools_by_name(names: list[str]) -> list[Tool]:
    allow = set(names)
    return [tool for tool in get_all_tools() if tool.name in allow]


def exclude_tools_by_name(names: list[str]) -> list[Tool]:
    deny = set(names)
    return [tool for tool in get_all_tools() if tool.name not in deny]


def generate_tool_summary() -> str:
    tools = get_all_tools()
    if not tools:
        return "(No tools registered)"

    lines = ["Available tools:"]
    for tool in tools:
        desc = tool.description({}) if callable(tool.description) else tool.description
        lines.append(f"  - {tool.name}: {desc}")
    return "\n".join(lines)
