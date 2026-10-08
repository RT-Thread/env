# -*- coding: utf-8 -*-
"""Kconfig helpers for menuconfig/defconfig."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import config
from config_file import is_package_metadata, read_config, write_header


@dataclass
class KconfigPaths:
    project_root: str
    config_header: str = config.CONFIG_HEADER

    @property
    def config_file(self) -> str:
        return os.path.join(self.project_root, '.config')

    @property
    def config_old(self) -> str:
        return os.path.join(self.project_root, '.config.old')

    def resolve_pkg_dir(self) -> Optional[str]:
        pkg_dir = os.path.join(self.project_root, 'packages')
        return pkg_dir if os.path.exists(pkg_dir) else None


class KconfigManager:
    def __init__(self, project_root: str, config_header: str = config.CONFIG_HEADER) -> None:
        self.paths = KconfigPaths(os.path.abspath(project_root), config_header)

    def menuconfig(self) -> None:
        self._check_kconfiglib()
        self._exclude_utestcases()

        import kconfiglib
        import menuconfig
        import curses

        self._fix_locale()

        try:
            menuconfig.menuconfig(kconfiglib.Kconfig('Kconfig', suppress_traceback=True))
        except curses.error as exc:
            if not os.path.isfile(self.paths.config_file):
                raise
            if 'nocbreak()' not in str(exc):
                print("警告: menuconfig 退出异常: %s" % exc)
        except Exception as exc:
            if not os.path.isfile(self.paths.config_file):
                raise
            print("警告: menuconfig 退出异常: %s" % exc)

        self._sync_proj_config()

    def defconfig(self) -> None:
        self._check_kconfiglib()
        self._exclude_utestcases()

        import kconfiglib

        kconf = kconfiglib.Kconfig('Kconfig', suppress_traceback=True)
        print(kconf.load_config('.config'))
        print(kconf.write_config())
        self._mk_proj_config(self.paths.config_file)

    def _sync_proj_config(self) -> None:
        if not os.path.isfile(self.paths.config_file):
            raise SystemExit(-1)

        if os.path.isfile(self.paths.config_old):
            diff_eq = Path(self.paths.config_file).read_bytes() == Path(self.paths.config_old).read_bytes()
        else:
            diff_eq = False

        if not diff_eq:
            shutil.copyfile(self.paths.config_file, self.paths.config_old)
            self._mk_proj_config(self.paths.config_file)
        elif not os.path.isfile(self.paths.config_header):
            self._mk_proj_config(self.paths.config_file)

    def _mk_proj_config(self, filename: str) -> None:
        if not os.path.isfile(filename):
            print('open config:%s failed' % filename)
            return

        write_header(read_config(filename), self.paths.config_header, 'PROJ_CONFIG_H__')

    def _exclude_utestcases(self) -> None:
        kconfig_path = os.path.join(self.paths.project_root, 'Kconfig')
        if os.path.isfile(os.path.join(self.paths.project_root, 'Kconfig.utestcases')):
            return
        if not os.path.isfile(kconfig_path):
            return

        with open(kconfig_path, 'r', encoding='utf-8') as handle:
            data = handle.readlines()
        with open(kconfig_path, 'w', encoding='utf-8') as handle:
            for line in data:
                if 'Kconfig.utestcases' not in line:
                    handle.write(line)

    def _check_kconfiglib(self) -> None:
        try:
            import kconfiglib  # noqa: F401
        except ImportError as exc:
            print("\033[1;31m**ERROR**: Failed to import kconfiglib, " + str(exc))
            print("")
            print("You may need to install it using:")
            print("    pip install kconfiglib\033[0m")
            print("")
            sys.exit(1)

        pkg_dir = self.paths.resolve_pkg_dir()
        if pkg_dir and os.path.exists(pkg_dir):
            os.environ['PKGS_DIR'] = pkg_dir
        else:
            print("\033[1;33m**WARNING**: PKGS_DIR not found, please install ENV tools\033[0m")

    @staticmethod
    def _fix_locale() -> None:
        import locale

        try:
            locale.setlocale(locale.LC_ALL, '')
        except locale.Error:
            locale.setlocale(locale.LC_ALL, 'C')

    @staticmethod
    def _is_pkg_special_config(config_str: str) -> bool:
        return is_package_metadata(config_str)


def menuconfig(project_root: str) -> None:
    KconfigManager(project_root).menuconfig()


def defconfig(project_root: str) -> None:
    KconfigManager(project_root).defconfig()
