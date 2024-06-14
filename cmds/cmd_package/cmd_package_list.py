# -*- coding:utf-8 -*-
#
# File      : cmd_package.py
# This file is part of RT-Thread RTOS
# COPYRIGHT (C) 2006 - 2020, RT-Thread Development Team
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Change Logs:
# Date           Author          Notes
# 2020-04-08     SummerGift      Optimize program structure
#

import os
import platform
import kconfig
from package import PackageOperation
from vars import Import


def get_packages():
    """Get the packages list in env.

    Read the.config file in the BSP directory,
    and return the version number of the selected package.
    """

    config_file = '.config'
    pkgs_root = Import('pkgs_root')
    packages = []
    if not os.path.isfile(config_file):
        print(
            "\033[1;31;40mWarning: Can't find .config.\033[0m"
            '\033[1;31;40mYou should use <menuconfig> command to config bsp first.\033[0m'
        )

        return packages

    packages = kconfig.parse(config_file)

    for pkg in packages:
        pkg_path = pkg['path']
        if pkg_path[0] == '/' or pkg_path[0] == '\\':
            pkg_path = pkg_path[1:]

        # parse package to get information
        package = PackageOperation()
        pkg_path = os.path.join(pkgs_root, pkg_path, 'package.json')
        package.parse(pkg_path)

        # update package name
        package_name_in_json = package.get_name()
        pkg['name'] = package_name_in_json

    return packages


def list_packages():
    """Print the packages list in env.

    Read the.config file in the BSP directory,
    and list the version number of the selected package.
    """

    config_file = '.config'
    pkgs_root = Import('pkgs_root')

    if not os.path.isfile(config_file):
        if platform.system() == "Windows":
            os.system('chcp 65001  > nul')

        print("\033[1;31;40mWarning: Can't find .config.\033[0m")
        print('\033[1;31;40mYou should use <menuconfig> command to config bsp first.\033[0m')

        if platform.system() == "Windows":
            os.system('chcp 437  > nul')

        return

    packages = kconfig.parse(config_file)

    for pkg in packages:
        package = PackageOperation()
        pkg_path = pkg['path']
        if pkg_path[0] == '/' or pkg_path[0] == '\\':
            pkg_path = pkg_path[1:]

        pkg_path = os.path.join(pkgs_root, pkg_path, 'package.json')
        package.parse(pkg_path)

        package_name_in_json = package.get_name().encode("utf-8")
        print("package name : %s, ver : %s " % (package_name_in_json, pkg['ver'].encode("utf-8")))

    if not packages:
        print("Packages list is empty.")
        print('You can use < menuconfig > command to select online packages.')
        print('Then use < pkgs --update > command to install them.')
    return
