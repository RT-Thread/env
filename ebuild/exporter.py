# -*- coding: utf-8 -*-
"""Project exporter implementations."""

from __future__ import annotations

import json
import os
from typing import Optional, TYPE_CHECKING

from . import config

if TYPE_CHECKING:
    from .system import BuildSystem


class ProjectExporter:
    def __init__(self, build: 'BuildSystem') -> None:
        self.build = build

    def export(self, target: str, output_dir: Optional[str] = None) -> bool:
        name = (target or '').lower()
        output_dir = output_dir or self.build.project_root

        if name in ('vscode', 'vsc'):
            return self._export_vscode(output_dir)
        if name == 'cmake':
            return self._export_cmake(output_dir)
        if name in ('mdk', 'mdk4', 'mdk5', 'keil'):
            return self._export_keil(name)
        raise ValueError(f"Unknown project target: {target}")

    def _export_vscode(self, output_dir: str) -> bool:
        info = self.build.registry.project_info()
        vscode_dir = os.path.join(output_dir, '.vscode')
        os.makedirs(vscode_dir, exist_ok=True)

        compiler = self.build.env.get('CC', '') if self.build.env else ''
        vscode_config = {
            "configurations": [
                {
                    "name": "Project",
                    "includePath": ["${workspaceFolder}/**"] + info['includes'],
                    "defines": info['defines'],
                    "compilerPath": compiler,
                    "cStandard": "c99",
                    "cppStandard": "c++11"
                }
            ],
            "version": 4
        }
        with open(os.path.join(vscode_dir, 'c_cpp_properties.json'), 'w', encoding='utf-8') as handle:
            json.dump(vscode_config, handle, indent=4)

        tasks = {
            "version": "2.0.0",
            "tasks": [
                {
                    "label": "build",
                    "type": "shell",
                    "command": "scons",
                    "problemMatcher": "$gcc",
                    "group": {"kind": "build", "isDefault": True}
                },
                {"label": "clean", "type": "shell", "command": "scons -c", "problemMatcher": "$gcc"}
            ]
        }
        with open(os.path.join(vscode_dir, 'tasks.json'), 'w', encoding='utf-8') as handle:
            json.dump(tasks, handle, indent=4)

        launch = {
            "version": "0.2.0",
            "configurations": [
                {
                    "name": "Cortex Debug",
                    "type": "cortex-debug",
                    "request": "launch",
                    "cwd": "${workspaceRoot}",
                    "executable": "${workspaceRoot}/" + config.TARGET_NAME,
                    "servertype": "openocd",
                    "device": "STM32F103C8"
                }
            ]
        }
        with open(os.path.join(vscode_dir, 'launch.json'), 'w', encoding='utf-8') as handle:
            json.dump(launch, handle, indent=4)

        settings = {
            "files.associations": {
                "*.h": "c",
                "*.c": "c",
                "*.cpp": "cpp",
                "*.cc": "cpp",
                "*.cxx": "cpp"
            }
        }
        with open(os.path.join(vscode_dir, 'settings.json'), 'w', encoding='utf-8') as handle:
            json.dump(settings, handle, indent=4)

        return True

    def _export_cmake(self, output_dir: str) -> bool:
        info = self.build.registry.project_info()
        lines = [
            "cmake_minimum_required(VERSION 3.10)",
            "",
            f"project({config.PROJECT_NAME} C CXX ASM)",
            "set(CMAKE_C_STANDARD 99)",
            "set(CMAKE_CXX_STANDARD 11)",
            "",
            "set(SOURCES"
        ]
        for src in info['sources']:
            lines.append(f"    {src}")
        lines.extend([")", ""])

        lines.append("add_executable(${PROJECT_NAME} ${SOURCES})")
        lines.append("")

        if info['includes']:
            lines.append("target_include_directories(${PROJECT_NAME} PRIVATE")
            for inc in info['includes']:
                lines.append(f"    {inc}")
            lines.extend([")", ""])

        if info['defines']:
            lines.append("target_compile_definitions(${PROJECT_NAME} PRIVATE")
            for define in info['defines']:
                lines.append(f"    {define}")
            lines.extend([")", ""])

        if info['libs']:
            lines.append("target_link_libraries(${PROJECT_NAME}")
            for lib in info['libs']:
                lines.append(f"    {lib}")
            lines.append(")")

        with open(os.path.join(output_dir, 'CMakeLists.txt'), 'w', encoding='utf-8') as handle:
            handle.write('\n'.join(lines))

        return True

    def _export_keil(self, target: str) -> bool:
        from .targets.keil import KeilProjectGenerator

        groups = self.build.registry.project_info()['groups']
        generator = KeilProjectGenerator(self.build.env, config.PROJECT_NAME)
        generator.generate(target, groups)
        return True
