"""Skills subsystem."""

from eagent.skills.loader import (
    load_all_skills,
    load_skills_from_dir,
    parse_frontmatter,
    parse_skill_file,
)
from eagent.skills.skill_tool import (
    build_skill_tool,
    format_skill_listing,
    get_loaded_skills,
    initialize_skills,
    reset_skills,
    set_skill_query_params,
)
from eagent.skills.types import SkillDefinition, SkillLoadResult

__all__ = [
    "SkillDefinition",
    "SkillLoadResult",
    "parse_frontmatter",
    "parse_skill_file",
    "load_skills_from_dir",
    "load_all_skills",
    "initialize_skills",
    "get_loaded_skills",
    "reset_skills",
    "set_skill_query_params",
    "format_skill_listing",
    "build_skill_tool",
]
