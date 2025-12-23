# -*- coding: utf-8 -*-
"""Attachconfig support for SCons --attach."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Dict, List, Optional

from SCons.Script import GetOption

from . import config
from .kconfig import defconfig


@dataclass
class AttachConfigPaths:
    project_root: str
    config_header: str = config.CONFIG_HEADER

    @property
    def config_file(self) -> str:
        return os.path.join(self.project_root, '.config')

    @property
    def config_backup(self) -> str:
        return self.config_file + '.origin'

    @property
    def config_header_file(self) -> str:
        return os.path.join(self.project_root, self.config_header)

    @property
    def config_header_backup(self) -> str:
        return self.config_header_file + '.origin'

    @property
    def attach_dir(self) -> str:
        return os.path.join(self.project_root, '.ci', 'attachconfig')


class AttachConfigRepository:
    def __init__(self, attach_dir: str) -> None:
        self.attach_dir = attach_dir
        self.projects: Dict[str, Dict] = {}

    def load(self) -> None:
        if not os.path.isdir(self.attach_dir):
            return
        for root, _, files in os.walk(self.attach_dir):
            for filename in files:
                if not filename.endswith('attachconfig.yml'):
                    continue
                path = os.path.join(root, filename)
                content = self._load_yaml(path)
                if isinstance(content, dict):
                    self.projects.update(content)

    def list_names(self) -> List[str]:
        return sorted([name for name, details in self.projects.items() if details and details.get('kconfig')])

    def collect_kconfig(self, name: str) -> List[str]:
        return self._collect_kconfig([name])

    def _collect_kconfig(self, names: List[str], seen: Optional[set] = None) -> List[str]:
        if seen is None:
            seen = set()
        lines: List[str] = []
        for item in names:
            if item in seen:
                print(f"::error::There are some problems with attachconfig depend: {item}")
                continue
            seen.add(item)
            detail = self.projects.get(item)
            if not detail:
                continue
            deps = detail.get('depends') or []
            if deps:
                lines.extend(self._collect_kconfig(deps, seen))
            if detail.get('kconfig'):
                lines.extend(detail.get('kconfig'))
        return lines

    @staticmethod
    def _load_yaml(path: str):
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("Attachconfig requires PyYAML, please install pyyaml.") from exc

        with open(path, 'r', encoding='utf-8') as handle:
            return yaml.safe_load(handle)


class AttachConfigManager:
    def __init__(self, project_root: str) -> None:
        self.paths = AttachConfigPaths(os.path.abspath(project_root))
        self.repo = AttachConfigRepository(self.paths.attach_dir)

    def run(self) -> None:
        option = GetOption('attach')
        if not option:
            return
        self.repo.load()

        if option == '?':
            self._print_available()
            return
        if option == 'default':
            self._restore_default()
            return
        self._apply(option)

    def _print_available(self) -> None:
        names = self.repo.list_names()
        if not names:
            print("AttachConfig empty.")
            return
        print("\033[32m✅ AttachConfig has: \033[0m")
        prefix = names[0].split('.', 1)[0]
        for name in names:
            section = name.split('.', 1)[0]
            if section != prefix:
                print("\033[42m \033[30m------" + section + "------\033[0m")
                prefix = section
            print(name)

    def _restore_default(self) -> None:
        restored = False
        if os.path.exists(self.paths.config_backup):
            shutil.copyfile(self.paths.config_backup, self.paths.config_file)
            os.remove(self.paths.config_backup)
            restored = True
        if os.path.exists(self.paths.config_header_backup):
            shutil.copyfile(self.paths.config_header_backup, self.paths.config_header_file)
            os.remove(self.paths.config_header_backup)
            restored = True
        if restored:
            print(f"\033[32m✅ Default .config and {self.paths.config_header} recovery success!\033[0m")
        else:
            print("AttachConfig: no backup files to restore.")

    def _apply(self, name: str) -> None:
        lines = self.repo.collect_kconfig(name)
        if not lines:
            print("❌\033[31m Without this AttachConfig:" + name + "\033[0m")
            return

        if not os.path.exists(self.paths.config_backup):
            shutil.copyfile(self.paths.config_file, self.paths.config_backup)
        if not os.path.exists(self.paths.config_header_backup):
            if os.path.exists(self.paths.config_header_file):
                shutil.copyfile(self.paths.config_header_file, self.paths.config_header_backup)

        with open(self.paths.config_file, 'a', encoding='utf-8') as destination:
            for line in lines:
                destination.write(line + '\n')

        defconfig(self.paths.project_root)
        print("\033[32m✅ AttachConfig add success!\033[0m")


def GenAttachConfigProject(project_root: Optional[str] = None) -> None:
    root = project_root or os.getcwd()
    AttachConfigManager(root).run()
