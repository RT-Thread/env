# -*- coding: utf-8 -*-
"""Shared defaults for the build scripts."""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from SCons import cpp as scons_cpp
DEFAULT_PROJECT_NAME = "project"
PROJECT_NAME = DEFAULT_PROJECT_NAME

DEFAULT_TARGET_NAME = f"{PROJECT_NAME}.elf"
TARGET_NAME = DEFAULT_TARGET_NAME

CONFIG_HEADER = "proj_config.h"


def resolve_project_root(explicit_root=None):
    root = explicit_root or os.getcwd()
    return os.path.abspath(root)


class ConfigType(Enum):
    """Configuration value types."""
    BOOLEAN = "boolean"
    INTEGER = "integer"
    STRING = "string"
    UNDEFINED = "undefined"


@dataclass
class ConfigOption:
    """Configuration option with metadata."""
    name: str
    value: Any
    type: ConfigType
    line_number: int = 0
    comment: str = ""

    def as_bool(self) -> bool:
        """Get value as boolean."""
        if self.type == ConfigType.BOOLEAN:
            return bool(self.value)
        if self.type == ConfigType.INTEGER:
            return self.value != 0
        if self.type == ConfigType.STRING:
            return bool(self.value)
        return False

    def as_int(self) -> int:
        """Get value as integer."""
        if self.type == ConfigType.INTEGER:
            return int(self.value)
        if self.type == ConfigType.BOOLEAN:
            return 1 if self.value else 0
        if self.type == ConfigType.STRING:
            try:
                return int(self.value)
            except ValueError:
                return 0
        return 0

    def as_str(self) -> str:
        """Get value as string."""
        if self.type == ConfigType.STRING:
            return self.value
        return str(self.value)


class ConfigParser:
    """Parser for config header files."""

    def __init__(self):
        self.options: Dict[str, ConfigOption] = {}

    def parse_file(self, filepath: str) -> Dict[str, ConfigOption]:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Configuration file not found: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as handle:
            content = handle.read()

        return self.parse_content(content)

    def parse_content(self, content: str) -> Dict[str, ConfigOption]:
        clean_content = self._strip_comments(content)
        preprocessor = _ConfigPreProcessor(self)
        preprocessor.process_contents(clean_content)
        return self.options

    def _parse_value(self, value: str) -> tuple:
        if not value or value == '1':
            return (True, ConfigType.BOOLEAN)

        try:
            return (int(value, 0), ConfigType.INTEGER)
        except ValueError:
            pass

        if value.startswith('"') and value.endswith('"'):
            return (value[1:-1], ConfigType.STRING)

        return (value, ConfigType.STRING)

    @staticmethod
    def _strip_comments(content: str) -> str:
        result: List[str] = []
        index = 0
        length = len(content)
        in_block = False
        in_line = False
        in_string = False

        while index < length:
            char = content[index]
            next_char = content[index + 1] if index + 1 < length else ''

            if in_line:
                if char == '\n':
                    in_line = False
                    result.append(char)
                index += 1
                continue

            if in_block:
                if char == '*' and next_char == '/':
                    in_block = False
                    index += 2
                    continue
                if char == '\n':
                    result.append(char)
                index += 1
                continue

            if in_string:
                result.append(char)
                if char == '\\' and next_char:
                    result.append(next_char)
                    index += 2
                    continue
                if char == '"':
                    in_string = False
                index += 1
                continue

            if char == '"':
                in_string = True
                result.append(char)
                index += 1
                continue

            if char == '/' and next_char == '/':
                in_line = True
                index += 2
                continue

            if char == '/' and next_char == '*':
                in_block = True
                index += 2
                continue

            result.append(char)
            index += 1

        return ''.join(result)


class _ConfigPreProcessor(scons_cpp.PreProcessor):
    def __init__(self, parser: ConfigParser) -> None:
        super().__init__(depth=0)
        self._parser = parser

    def do_define(self, t) -> None:
        _, name, args, expansion = t
        if args:
            super().do_define(t)
            self._parser.options[name] = ConfigOption(
                name=name,
                value=None,
                type=ConfigType.UNDEFINED,
            )
            return

        raw_value = (expansion or '').strip()
        parsed_value, value_type = self._parser._parse_value(raw_value)
        self.cpp_namespace[name] = parsed_value
        self._parser.options[name] = ConfigOption(
            name=name,
            value=parsed_value,
            type=value_type,
        )

    def do_undef(self, t) -> None:
        name = t[1]
        self._parser.options.pop(name, None)
        self.cpp_namespace.pop(name, None)

    def do_include(self, t) -> None:
        return

    do_include_next = do_include
    do_import = do_include


class ConfigManager:
    """Configuration manager for build system."""

    def __init__(self):
        self.parser = ConfigParser()
        self.options: Dict[str, ConfigOption] = {}
        self.cache: Dict[str, bool] = {}

    def load_from_file(self, filepath: str) -> None:
        self.options = self.parser.parse_file(filepath)
        self.cache.clear()

    def get_option(self, name: str) -> Optional[ConfigOption]:
        return self.options.get(name)

    def get_all_options(self) -> Dict[str, Any]:
        return {name: opt.value for name, opt in self.options.items()}

    def get_value(self, name: str, default: Any = None) -> Any:
        option = self.options.get(name)
        if option:
            return option.value
        return default

    def get_dependency(self, depend: Union[str, List[str]]) -> bool:
        if not depend:
            return True

        if isinstance(depend, str):
            depend = [depend]

        cache_key = ','.join(sorted(depend))
        if cache_key in self.cache:
            return self.cache[cache_key]

        result = all(self._check_single_dependency(item) for item in depend)
        self.cache[cache_key] = result
        return result

    def _check_single_dependency(self, name: str) -> bool:
        option = self.options.get(name)
        if not option:
            return False

        if option.type == ConfigType.INTEGER:
            return option.value != 0

        return option.as_bool()
