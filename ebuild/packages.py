# -*- coding: utf-8 -*-
"""Package.json based component builder."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .helpers import normalize_list

if TYPE_CHECKING:
    from .system import BuildSystem


class PackageBuilder:
    def __init__(self, build: 'BuildSystem') -> None:
        self.build = build

    def build_package(self, package_path: Optional[str] = None) -> List[Any]:
        env = self.build.env
        if env is None:
            raise RuntimeError('BuildPackage requires an initialized SCons environment.')

        if package_path is None:
            package_path = os.path.join(self.build.get_current_dir(), 'package.json')
        elif os.path.isdir(package_path):
            package_path = os.path.join(package_path, 'package.json')

        if not os.path.isfile(package_path):
            return []

        with open(package_path, 'r', encoding='utf-8') as handle:
            package = json.load(handle)

        if package.get('type') != 'rt-thread-component' or 'name' not in package:
            return []

        dependencies = normalize_list(package.get('dependencies'))
        if dependencies and not self._any_dependency_enabled(dependencies):
            return []

        defines = normalize_list(package.get('defines'))
        sources, includes = self._collect_sources(package_path, package.get('sources', []))
        return self.build.define_group(
            package['name'],
            sources,
            depend=dependencies,
            CPPPATH=includes,
            CPPDEFINES=defines,
        )

    def _any_dependency_enabled(self, deps: List[str]) -> bool:
        for dep in deps:
            if self.build.get_depend(dep):
                return True
        return False

    def _collect_sources(self, package_path: str, items: List[Dict[str, Any]]) -> tuple:
        base_dir = os.path.dirname(os.path.abspath(package_path))
        sources: List[str] = []
        includes: List[str] = []

        for item in items:
            item_deps = normalize_list(item.get('dependencies'))
            if item_deps and not self._any_dependency_enabled(item_deps):
                continue

            for inc in normalize_list(item.get('includes')):
                if os.path.isabs(inc) and os.path.isdir(inc):
                    includes.append(inc)
                else:
                    includes.append(os.path.abspath(os.path.join(base_dir, inc)))

            for pattern in normalize_list(item.get('files')):
                pattern_path = pattern if os.path.isabs(pattern) else os.path.join(base_dir, pattern)
                sources.extend(self.build.glob_files(pattern_path))

        return sources, includes
