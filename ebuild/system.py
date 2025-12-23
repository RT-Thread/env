# -*- coding: utf-8 -*-
"""SCons build system core."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from . import config
from .config import ConfigManager
from .exporter import ProjectExporter
from .groups import Group, GroupRegistry
from .helpers import merge_flags, normalize_defines, normalize_list
from .options import AddOptions
from .packages import PackageBuilder


@dataclass
class ToolchainSettings:
    cc_prefix: str = ""
    build_program: bool = True


class BuildSystem:
    _current: Optional['BuildSystem'] = None

    def __init__(self, env, workspace_root: Optional[str] = None, project_root: Optional[str] = None) -> None:
        if workspace_root is None:
            workspace_root = project_root
        self.env = env
        self.workspace_root = os.path.abspath(workspace_root or config.resolve_project_root())
        self.project_root = os.path.abspath(os.getcwd())
        self.config_header = config.CONFIG_HEADER

        self.config = ConfigManager()
        self.build_options: Dict[str, Any] = {}
        self.registry = GroupRegistry()
        self.packages = PackageBuilder(self)
        self.exporter = ProjectExporter(self)

        BuildSystem._current = self

    @classmethod
    def current(cls) -> Optional['BuildSystem']:
        return cls._current

    def setup(self) -> 'BuildSystem':
        AddOptions()
        self._prepare_environment()
        self._handle_attach()
        self._handle_menuconfig()
        self._load_config()
        self._apply_command_output()
        self.install_env()
        return self

    def install_env(self) -> None:
        env = self.env
        env['_BuildSystem'] = self

        def define_group(env, name: str, src: List[Any], depend: Any = None, **kwargs) -> List[Any]:
            return self.define_group(name, src, depend, **kwargs)

        def build_package(env, package_path: Optional[str] = None) -> List[Any]:
            return self.build_package(package_path)

        def bridge(env) -> List[Any]:
            return self.bridge()

        def glob(env, pattern: str):
            from SCons.Script import Glob

            try:
                return Glob(pattern)
            except Exception:
                return []

        def get_cc(env) -> str:
            return str(env.get('CC', ''))

        env.AddMethod(define_group, 'DefineGroup')
        env.AddMethod(build_package, 'BuildPackage')
        env.AddMethod(bridge, 'Bridge')
        env.AddMethod(lambda env, dep: self.get_depend(dep), 'GetDepend')
        env.AddMethod(glob, 'Glob')
        env.AddMethod(lambda env, pattern: self.glob_files(pattern), 'GlobFiles')
        env.AddMethod(lambda env, src, remove: self.src_remove(src, remove), 'SrcRemove')
        env.AddMethod(lambda env: self.get_current_dir(), 'GetCurrentDir')
        env.AddMethod(lambda env, target, objs=None: self.do_building(target, objs), 'DoBuilding')
        env.AddMethod(lambda env: self.build_options, 'GetBuildOptions')
        env.AddMethod(lambda env: self.workspace_root, 'GetProjectRoot')
        env.AddMethod(lambda env: self.project_root, 'GetBSPRoot')
        env.AddMethod(lambda env: self.workspace_root, 'GetRTTRoot')
        env.AddMethod(get_cc, 'GetCC')
        env.AddMethod(lambda env: self, 'GetContext')

    def define_group(self, name: str, src: List[Any], depend: Any = None, **kwargs) -> List[Any]:
        dependencies = [item for item in normalize_list(depend) if item]
        if not self.get_dependency(dependencies):
            return []

        src_list = self._normalize_sources(src)

        group = Group(
            name=name,
            sources=src_list,
            dependencies=dependencies,
            path=self.get_current_dir(),
            include_paths=normalize_list(kwargs.get('CPPPATH')),
            defines=normalize_defines(kwargs.get('CPPDEFINES')),
            libs=normalize_list(kwargs.get('LIBS')),
            lib_paths=normalize_list(kwargs.get('LIBPATH')),
            cflags=merge_flags(kwargs.get('CFLAGS'), kwargs.get('CCFLAGS')),
            cxxflags=merge_flags(kwargs.get('CXXFLAGS'), kwargs.get('CCFLAGS')),
            asflags=merge_flags(kwargs.get('ASFLAGS')),
            ldflags=merge_flags(kwargs.get('LINKFLAGS')),
            local_cflags=merge_flags(kwargs.get('LOCAL_CFLAGS'), kwargs.get('LOCAL_CCFLAGS')),
            local_cxxflags=merge_flags(kwargs.get('LOCAL_CXXFLAGS'), kwargs.get('LOCAL_CCFLAGS')),
            local_asflags=merge_flags(kwargs.get('LOCAL_ASFLAGS')),
            local_include_paths=normalize_list(kwargs.get('LOCAL_CPPPATH')),
            local_defines=normalize_defines(kwargs.get('LOCAL_CPPDEFINES')),
        )

        self.registry.add(group)

        objects = group.build(self.env)
        if kwargs.get('LIBRARY'):
            return self.env.Library(name, objects)
        return objects

    def build_package(self, package_path: Optional[str] = None) -> List[Any]:
        return self.packages.build_package(package_path)

    def bridge(self) -> List[Any]:
        from SCons.Script import SConscript

        base_dir = self.get_current_dir()
        if not base_dir or not os.path.isdir(base_dir):
            return []

        env = self.env
        groups: List[Any] = []
        for name in sorted(os.listdir(base_dir)):
            child_dir = os.path.join(base_dir, name)
            if not os.path.isdir(child_dir):
                continue
            script = os.path.join(child_dir, 'SConscript')
            if not os.path.isfile(script):
                continue
            group = SConscript(script)
            if not group:
                continue
            if isinstance(group, list):
                groups.extend(group)
            else:
                groups.append(group)

        return groups

    def export_project(self, target: str, output_dir: Optional[str] = None) -> bool:
        return self.exporter.export(target, output_dir)

    def prepare_building(self) -> List[Any]:
        return self.merge_groups()

    def do_building(self, target: Optional[str], objs: Optional[List[Any]] = None) -> Optional[Any]:
        from SCons.Script import Default, GetOption

        if objs is None:
            objs = self.prepare_building()

        export_target = GetOption('target')
        if export_target:
            self.export_project(export_target)
            raise SystemExit(0)

        if not target:
            Default(objs)
            return None

        program = self.env.Program(target, objs)
        targets = [program]

        bin_name = self.env.get('RTBOOT_BIN')
        if bin_name:
            bin_file = self.env.Command(bin_name, program, "$OBJCOPY -O binary $SOURCE $TARGET")
            targets.append(bin_file)

        if self.env.get('SIZE'):
            self.env.AddPostAction(program, "$SIZE $TARGET")
        Default(targets)
        return program

    def get_dependency(self, depend: Any) -> bool:
        return self.config.get_dependency(depend)

    def get_depend(self, depend: Any) -> bool:
        return self.get_dependency(depend)

    def get_current_dir(self) -> str:
        from SCons.Script import Dir, File

        conscript = File('SConscript')
        if conscript.exists():
            return os.path.dirname(conscript.rfile().abspath)
        return Dir('.').abspath

    def glob_files(self, pattern: str) -> List[str]:
        from SCons.Script import Glob

        try:
            return sorted(Glob(pattern, strings=True))
        except Exception:
            return []

    def src_remove(self, src: List[str], remove: List[str]) -> None:
        if not src:
            return
        if not isinstance(remove, list):
            remove = [remove]

        import fnmatch

        for item in remove:
            matches = [s for s in src if fnmatch.fnmatch(str(s), item)]
            for match in matches:
                src.remove(match)

    def merge_groups(self) -> List[Any]:
        return self.registry.merge_objects()

    def apply_toolchain_options(self, base_cflags: Optional[List[str]] = None) -> ToolchainSettings:
        from SCons.Script import GetOption

        cflags = list(base_cflags) if base_cflags else []

        def option_value(name: str, default: str = "") -> str:
            value = GetOption(name)
            return value or default

        cc_prefix = option_value('cross-compile', '')
        if cc_prefix:
            self.env['CC'] = cc_prefix + 'gcc'
            self.env['AR'] = cc_prefix + 'ar'
            self.env['AS'] = cc_prefix + 'gcc'
            self.env['RANLIB'] = cc_prefix + 'ranlib'
            cflags.append('-ffreestanding')

        cpu = option_value('cpu', '')
        if cpu:
            cflags.append(f'-mcpu={cpu}')

        fpu = option_value('fpu', '')
        if fpu:
            cflags.append(f'-mfpu={fpu}')

        float_abi = option_value('float-abi', '')
        if float_abi:
            cflags.append(f'-mfloat-abi={float_abi}')

        if cflags:
            self.env.Append(CFLAGS=cflags)

        build_program = not cc_prefix
        return ToolchainSettings(cc_prefix=cc_prefix, build_program=build_program)

    def _prepare_environment(self) -> None:
        self.env['PROJECT_ROOT'] = self.workspace_root
        self.env.setdefault('RTT_ROOT', self.workspace_root)
        self.env['BSP_ROOT'] = self.project_root

        tools_path = os.path.join(self.workspace_root, 'tools')
        if tools_path not in sys.path:
            sys.path.insert(0, tools_path)

    def _apply_command_output(self) -> None:
        from SCons.Script import GetOption

        if GetOption('verbose'):
            return

        self.env.Replace(
            ARCOMSTR="AR $TARGET",
            ASCOMSTR="AS $TARGET",
            ASPPCOMSTR="AS $TARGET",
            CCCOMSTR="CC $TARGET",
            CXXCOMSTR="CXX $TARGET",
            LINKCOMSTR="LINK $TARGET",
            RANLIBCOMSTR="RANLIB $TARGET",
        )

    def _handle_menuconfig(self) -> None:
        from SCons.Script import GetOption

        if GetOption('menuconfig'):
            from .kconfig import menuconfig

            menuconfig(self.workspace_root)
            raise SystemExit(0)

    def _handle_attach(self) -> None:
        from SCons.Script import GetOption

        if GetOption('attach'):
            from .attach import GenAttachConfigProject

            GenAttachConfigProject(self.workspace_root)
            raise SystemExit(0)

    def _load_config(self) -> None:
        config_path = os.path.join(self.project_root, self.config_header)
        if not os.path.exists(config_path):
            print(f"{self.config_header} not found, run: scons --menuconfig")
            raise SystemExit(1)
        self.config.load_from_file(config_path)
        self.build_options = self.config.get_all_options()

    def _normalize_sources(self, src: Any) -> List[Any]:
        if src is None:
            return []
        src_list = src if isinstance(src, list) else [src]
        result: List[Any] = []
        seen = set()

        for item in src_list:
            if item is None:
                continue
            node = self.env.File(item) if isinstance(item, str) else item
            key = getattr(node, 'abspath', None) or str(node)
            if key in seen:
                continue
            seen.add(key)
            result.append(node)

        return result


def prepare(env, workspace_root: Optional[str] = None, project_root: Optional[str] = None, config_module=None) -> BuildSystem:
    if workspace_root is None:
        workspace_root = project_root
    build = BuildSystem(env, workspace_root).setup()
    from SCons.Script import Export
    Export(env=env)
    if config_module is not None:
        env['config'] = config_module
        project_name = getattr(config_module, 'PROJECT_NAME', None)
        if project_name:
            config.PROJECT_NAME = str(project_name)
        target_name = getattr(config_module, 'TARGET_NAME', None)
        if target_name:
            config.TARGET_NAME = str(target_name)
        else:
            if project_name:
                config.TARGET_NAME = f"{config.PROJECT_NAME}.elf"
        if hasattr(config_module, 'setup_project'):
            config_module.setup_project(env, build.project_root)
        elif hasattr(config_module, 'MCU_SERIES'):
            from .toolchain import setup_project

            setup_project(env, build.project_root, config_module)
    return build
