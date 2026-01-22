# -*- coding: utf-8 -*-
"""Group model and registry."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .helpers import defines_to_list, source_to_path


@dataclass
class Group:
    name: str
    sources: List[Any]
    dependencies: List[str] = field(default_factory=list)
    path: str = ""

    include_paths: List[str] = field(default_factory=list)
    defines: Dict[str, str] = field(default_factory=dict)
    libs: List[str] = field(default_factory=list)
    lib_paths: List[str] = field(default_factory=list)

    cflags: List[str] = field(default_factory=list)
    cxxflags: List[str] = field(default_factory=list)
    asflags: List[str] = field(default_factory=list)
    ldflags: List[str] = field(default_factory=list)

    local_include_paths: List[str] = field(default_factory=list)
    local_defines: Dict[str, str] = field(default_factory=dict)
    local_cflags: List[str] = field(default_factory=list)
    local_cxxflags: List[str] = field(default_factory=list)
    local_asflags: List[str] = field(default_factory=list)

    objects: List[Any] = field(default_factory=list)

    def build(self, env) -> List[Any]:
        if not self.sources:
            return []

        build_env = env.Clone() if self._has_local_options() else env
        self._apply_options(build_env)

        objects: List[Any] = []
        build_root = self._build_root(build_env)
        for src in self.sources:
            source_node = self._resolve_source_node(build_env, src)
            if self._is_object_node(source_node, build_env):
                objects.append(source_node)
                continue

            obj_target = self._object_target(source_node, build_env, build_root)
            obj = build_env.Object(target=obj_target, source=source_node)
            objects.extend(obj if isinstance(obj, list) else [obj])

        self.objects = objects
        return objects

    def info(self) -> Dict[str, Any]:
        def norm_paths(paths: List[str]) -> List[str]:
            return [os.path.abspath(p) for p in paths]

        return {
            'name': self.name,
            'src': [self._source_path(src) for src in self.sources],
            'CPPPATH': norm_paths(self.include_paths),
            'CPPDEFINES': defines_to_list(self.defines),
            'LOCAL_CPPPATH': norm_paths(self.local_include_paths),
            'LOCAL_CPPDEFINES': defines_to_list(self.local_defines),
            'CFLAGS': ' '.join(self.cflags),
            'CCFLAGS': ' '.join(self.cflags),
            'CXXFLAGS': ' '.join(self.cxxflags),
            'ASFLAGS': ' '.join(self.asflags),
            'LINKFLAGS': ' '.join(self.ldflags),
            'LIBS': self.libs,
            'LIBPATH': self.lib_paths,
        }

    def _has_local_options(self) -> bool:
        return bool(
            self.local_include_paths
            or self.local_defines
            or self.local_cflags
            or self.local_cxxflags
            or self.local_asflags
        )

    def _apply_options(self, env) -> None:
        if self.include_paths:
            env.AppendUnique(CPPPATH=[os.path.abspath(p) for p in self.include_paths])
        if self.defines:
            env.AppendUnique(CPPDEFINES=self.defines)
        if self.cflags:
            env.AppendUnique(CFLAGS=self.cflags)
        if self.cxxflags:
            env.AppendUnique(CXXFLAGS=self.cxxflags)
        if self.asflags:
            env.AppendUnique(ASFLAGS=self.asflags)
        if self.ldflags:
            env.AppendUnique(LINKFLAGS=self.ldflags)
        if self.libs:
            env.AppendUnique(LIBS=self.libs)
        if self.lib_paths:
            env.AppendUnique(LIBPATH=[os.path.abspath(p) for p in self.lib_paths])

        if self.local_include_paths:
            env.AppendUnique(CPPPATH=[os.path.abspath(p) for p in self.local_include_paths])
        if self.local_defines:
            env.AppendUnique(CPPDEFINES=self.local_defines)
        if self.local_cflags:
            env.AppendUnique(CFLAGS=self.local_cflags)
        if self.local_cxxflags:
            env.AppendUnique(CXXFLAGS=self.local_cxxflags)
        if self.local_asflags:
            env.AppendUnique(ASFLAGS=self.local_asflags)

    def _source_path(self, src: Any) -> str:
        return source_to_path(src)

    @staticmethod
    def _project_root(env) -> str:
        if hasattr(env, 'GetProjectRoot'):
            return os.path.abspath(env.GetProjectRoot())
        if hasattr(env, 'GetWorkspaceRoot'):
            return os.path.abspath(env.GetWorkspaceRoot())
        return os.path.abspath(os.getcwd())

    def _build_root(self, env) -> str:
        return os.path.join(self._project_root(env), 'build')

    def _resolve_source_node(self, env, src: Any) -> Any:
        if isinstance(src, str):
            if os.path.isabs(src):
                return env.File(src)
            base_dir = self.path or os.getcwd()
            return env.File(os.path.join(base_dir, src))
        return src

    @staticmethod
    def _is_object_node(src: Any, env) -> bool:
        suffix = env.get('OBJSUFFIX', '.o')
        path = source_to_path(src)
        return path.endswith(suffix)

    def _object_target(self, src: Any, env, build_root: str) -> str:
        src_path = source_to_path(src)
        project_root = self._project_root(env)
        rel_path = os.path.relpath(src_path, project_root)
        if rel_path.startswith('..'):
            rel_path = os.path.join('_external', os.path.basename(src_path))
        rel_path = os.path.normpath(rel_path)
        rel_base, _ = os.path.splitext(rel_path)
        suffix = env.get('OBJSUFFIX', '.o')
        return os.path.join(build_root, rel_base + suffix)


class GroupRegistry:
    def __init__(self) -> None:
        self.groups: List[Group] = []

    def add(self, group: Group) -> None:
        self.groups.append(group)

    def merge_objects(self) -> List[Any]:
        objects: List[Any] = []
        for group in self.groups:
            objects.extend(group.objects)
        return objects

    def project_info(self) -> Dict[str, Any]:
        sources: List[str] = []
        includes: List[str] = []
        defines: List[str] = []
        libs: List[str] = []
        lib_paths: List[str] = []

        def append_unique(items: List[str], values: List[str]) -> None:
            for item in values:
                if item not in items:
                    items.append(item)

        for group in self.groups:
            info = group.info()
            sources.extend(info['src'])
            append_unique(includes, info['CPPPATH'])
            append_unique(includes, info['LOCAL_CPPPATH'])
            append_unique(defines, info['CPPDEFINES'])
            append_unique(defines, info['LOCAL_CPPDEFINES'])
            append_unique(libs, info['LIBS'])
            append_unique(lib_paths, info['LIBPATH'])

        return {
            'groups': [group.info() for group in self.groups],
            'sources': sources,
            'includes': includes,
            'defines': defines,
            'libs': libs,
            'lib_paths': lib_paths,
        }
