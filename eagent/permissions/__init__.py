"""Permission utilities."""

from eagent.permissions.engine import (
    PermissionContext,
    add_session_rule,
    check_permission,
    clear_session_rules,
    get_session_rules,
    is_read_only_command,
)
from eagent.permissions.modes import ModeRestrictions, get_mode_description, get_mode_restrictions
from eagent.permissions.path_validation import PathValidationResult, validate_path
from eagent.permissions.rules import load_project_rules, load_user_rules, match_rule

__all__ = [
    "PermissionContext",
    "add_session_rule",
    "get_session_rules",
    "clear_session_rules",
    "is_read_only_command",
    "check_permission",
    "ModeRestrictions",
    "get_mode_description",
    "get_mode_restrictions",
    "PathValidationResult",
    "validate_path",
    "load_project_rules",
    "load_user_rules",
    "match_rule",
]
