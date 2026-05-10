"""Built-in tools and registry."""

from eagent.tools.agent_tool import build_agent_tool, set_agent_query_params
from eagent.tools.ask import build_ask_tool
from eagent.tools.bash import build_bash_tool
from eagent.tools.bash_readonly import is_read_only_command, parse_command_parts
from eagent.tools.edit import build_edit_tool
from eagent.tools.glob_tool import build_glob_tool
from eagent.tools.grep_tool import build_grep_tool
from eagent.tools.notebook_edit import build_notebook_edit_tool
from eagent.tools.plan_mode import build_enter_plan_mode_tool, build_exit_plan_mode_tool
from eagent.tools.read import build_read_tool
from eagent.tools.registry import (
    exclude_tools_by_name,
    filter_tools_by_name,
    generate_tool_summary,
    get_all_tools,
    get_read_only_tool_names,
    get_tool_by_name,
    get_tool_count,
    has_tool_by_name,
    initialize_tools,
    register_dynamic_tools,
    register_tool,
    reset_registry,
)
from eagent.tools.todo import build_todo_tool
from eagent.tools.web_fetch import build_web_fetch_tool
from eagent.tools.web_search import build_web_search_tool
from eagent.tools.write import build_write_tool

__all__ = [
    "build_bash_tool",
    "build_read_tool",
    "build_edit_tool",
    "build_write_tool",
    "build_glob_tool",
    "build_grep_tool",
    "build_agent_tool",
    "set_agent_query_params",
    "build_ask_tool",
    "build_todo_tool",
    "build_web_fetch_tool",
    "build_web_search_tool",
    "build_enter_plan_mode_tool",
    "build_exit_plan_mode_tool",
    "build_notebook_edit_tool",
    "is_read_only_command",
    "parse_command_parts",
    "register_tool",
    "register_dynamic_tools",
    "get_all_tools",
    "get_tool_by_name",
    "has_tool_by_name",
    "get_tool_count",
    "initialize_tools",
    "reset_registry",
    "get_read_only_tool_names",
    "filter_tools_by_name",
    "exclude_tools_by_name",
    "generate_tool_summary",
]
