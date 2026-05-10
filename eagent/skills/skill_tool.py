"""Skill tool integration."""

from __future__ import annotations

from typing import Any

from eagent.core.types import QueryParams, Tool, ToolContext, ToolResult
from eagent.skills.loader import load_all_skills
from eagent.skills.types import SkillDefinition

_loaded_skills: list[SkillDefinition] = []
_initialized = False
_query_params: QueryParams | None = None


def set_skill_query_params(params: QueryParams | None) -> None:
    global _query_params
    _query_params = params


async def initialize_skills(cwd: str) -> None:
    global _loaded_skills, _initialized
    _loaded_skills = await load_all_skills(cwd)
    _initialized = True


def get_loaded_skills() -> list[SkillDefinition]:
    return list(_loaded_skills)


def reset_skills() -> None:
    global _loaded_skills, _initialized
    _loaded_skills = []
    _initialized = False


def format_skill_listing(skills: list[SkillDefinition]) -> str:
    if not skills:
        return ""
    lines = ["Available skills (invoke via Skill tool):", ""]
    for skill in skills:
        lines.append(f"  - {skill.name}: {skill.description}")
        if skill.when_to_use:
            lines.append(f"    When to use: {skill.when_to_use}")
        if skill.argument_hint:
            lines.append(f"    Arguments: {skill.argument_hint}")
        if skill.context == "fork":
            lines.append("    Execution: forked sub-agent")
    return "\n".join(lines)


def _find_skill(name: str) -> SkillDefinition | None:
    normalized = name[1:] if name.startswith("/") else name
    lookup = normalized.lower()
    for skill in _loaded_skills:
        if skill.name.lower() == lookup:
            return skill
    return None


def _skill_not_found(requested: str) -> str:
    if not _loaded_skills:
        return (
            f'Skill "{requested}" not found. No skills are loaded. '
            "Place skills under .agents/skills, ~/.agents/skills, or ~/.env/skills."
        )
    lines = [f'Skill "{requested}" not found. Available skills:']
    for skill in _loaded_skills:
        lines.append(f"  - {skill.name}: {skill.description}")
    return "\n".join(lines)


async def _execute_inline(skill: SkillDefinition, args: str) -> ToolResult:
    assert skill.get_prompt is not None
    prompt = await skill.get_prompt(args)
    return ToolResult(result=prompt)


async def _execute_fork(skill: SkillDefinition, args: str, context: ToolContext) -> ToolResult:
    if _query_params is None:
        return await _execute_inline(skill, args)

    from eagent.core.agent_loop import run_sub_agent

    assert skill.get_prompt is not None
    prompt = await skill.get_prompt(args)

    try:
        result = await run_sub_agent(
            prompt,
            _query_params,
            tools=skill.allowed_tools,
            max_turns=50,
            model=skill.model,
        )
        return ToolResult(result=result or "(Skill produced no output)")
    except Exception as exc:
        return ToolResult(result=f"Skill execution failed: {exc}", is_error=True)


async def _call(input_data: dict[str, Any], context: ToolContext) -> ToolResult:
    if not _initialized:
        await initialize_skills(context.cwd)

    skill_name = str(input_data.get("skill") or "").strip()
    args = str(input_data.get("args") or "")

    if not skill_name:
        return ToolResult(result="Error: skill name is required.", is_error=True)

    skill = _find_skill(skill_name)
    if skill is None:
        return ToolResult(result=_skill_not_found(skill_name), is_error=True)

    if skill.context == "fork":
        return await _execute_fork(skill, args, context)
    return await _execute_inline(skill, args)


def build_skill_tool() -> Tool:
    return Tool(
        name="Skill",
        description=(
            "Invoke a loaded skill by name. Skills are reusable prompt templates from "
            ".agents/skills, ~/.agents/skills, or ~/.env/skills."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "skill": {"type": "string"},
                "args": {"type": "string"},
            },
            "required": ["skill"],
            "additionalProperties": False,
        },
        call=_call,
        prompt=lambda: format_skill_listing(_loaded_skills),
        is_read_only=lambda _i: True,
        is_concurrency_safe=lambda _i: False,
        max_result_size_chars=120_000,
        user_facing_name=lambda input_data: f"Skill: {input_data.get('skill')}",
    )
