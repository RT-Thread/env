"""Slash command package."""

from eagent.commands.registry import execute_command, get_command_info_list, get_commands

__all__ = ["get_commands", "get_command_info_list", "execute_command"]
