# -*- coding: utf-8 -*-
"""Kconfig helpers for menuconfig/defconfig."""

from __future__ import annotations

import hashlib
import os
import re
import sys
from dataclasses import dataclass
from typing import Optional

from . import config


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

        import menuconfig
        import curses

        sys.argv = ['menuconfig', 'Kconfig']
        self._fix_locale()

        try:
            menuconfig._main()
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

        import defconfig

        sys.argv = ['defconfig', '--kconfig', 'Kconfig', '.config']
        defconfig.main()
        self._mk_proj_config(self.paths.config_file)

    def _sync_proj_config(self) -> None:
        if not os.path.isfile(self.paths.config_file):
            raise SystemExit(-1)

        if os.path.isfile(self.paths.config_old):
            diff_eq = self._file_md5(self.paths.config_file) == self._file_md5(self.paths.config_old)
        else:
            diff_eq = False

        if not diff_eq:
            self._copy_file(self.paths.config_file, self.paths.config_old)
            self._mk_proj_config(self.paths.config_file)
        elif not os.path.isfile(self.paths.config_header):
            self._mk_proj_config(self.paths.config_file)

    def _mk_proj_config(self, filename: str) -> None:
        if not os.path.isfile(filename):
            print('open config:%s failed' % filename)
            return

        with open(filename, 'r', encoding='utf-8') as config_file:
            lines = config_file.readlines()

        with open(self.paths.config_header, 'w', encoding='utf-8') as config_header:
            config_header.write('#ifndef PROJ_CONFIG_H__\n')
            config_header.write('#define PROJ_CONFIG_H__\n\n')

            empty_line = True
            for line in lines:
                line = line.lstrip(' ').replace('\n', '').replace('\r', '')
                if not line:
                    continue

                if line.startswith('#'):
                    if len(line) == 1:
                        if empty_line:
                            continue
                        config_header.write('\n')
                        empty_line = True
                        continue
                    if line.startswith('# CONFIG_'):
                        line = ' ' + line[9:]
                    else:
                        config_header.write('/*%s */\n' % line[1:])
                    empty_line = False
                    continue

                empty_line = False
                setting = line.split('=')
                if len(setting) < 2:
                    continue
                key = setting[0]
                if key.startswith('CONFIG_'):
                    key = key[7:]
                if self._is_pkg_special_config(key):
                    continue
                if setting[1] == 'y':
                    config_header.write('#define %s\n' % key)
                else:
                    value = re.findall(r"^.*?=(.*)$", line)[0]
                    config_header.write('#define %s %s\n' % (key, value))

            config_header.write('\n')
            config_header.write('#endif\n')

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
    def _file_md5(file_path: str) -> str:
        md5 = hashlib.new('md5')
        with open(file_path, 'r', encoding='utf-8') as handle:
            md5.update(handle.read().encode('utf8'))
        return md5.hexdigest()

    @staticmethod
    def _copy_file(src: str, dst: str) -> None:
        with open(src, 'r', encoding='utf-8') as handle:
            content = handle.read()
        with open(dst, 'w', encoding='utf-8') as handle:
            handle.write(content)

    @staticmethod
    def _is_pkg_special_config(config_str: str) -> bool:
        return config_str.startswith("PKG_") and (config_str.endswith('_PATH') or config_str.endswith('_VER'))


def menuconfig(project_root: str) -> None:
    KconfigManager(project_root).menuconfig()


def defconfig(project_root: str) -> None:
    KconfigManager(project_root).defconfig()
