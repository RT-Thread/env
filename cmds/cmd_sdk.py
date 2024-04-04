# -*- coding:utf-8 -*-
#
# File      : cmd_sdk.py
# This file is part of RT-Thread RTOS
# COPYRIGHT (C) 2024, RT-Thread Development Team
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
# 2024-04-04     bernard         the first version

import os
import json
from vars import Import

'''RT-Thread environment sdk setting'''

class MenuConfigArgs:
    menuconfig_fn = False
    menuconfig_g = False
    menuconfig_silent = False
    menuconfig_setting = False

def cmd(args):
    tools_kconfig_path = os.path.join(Import('env_root'), 'tools')

    from cmds import cmd_menuconfig
    from cmds.cmd_package import list_packages
    from cmds.cmd_package import get_packages
    from cmds.cmd_package import package_update

    args = MenuConfigArgs()
    # do menuconfig
    cmd_menuconfig.cmd(args)

    # update package
    package_update()

    # update sdk list information
    packages = get_packages()

    sdk_packages = []
    for item in packages:
        sdk_item = {}
        sdk_item['name'] = item['name']
        sdk_item['path'] = item['name'] + '-' + item['ver']

        sdk_packages.append(sdk_item)

    # write sdk_packages to sdk_list.json
    with open(os.path.join(tools_kconfig_path, 'sdk_list.json'), 'w', encoding='utf-8') as f:
        json.dump(sdk_packages, f, ensure_ascii=False, indent=4)

def add_parser(sub):
    parser = sub.add_parser('sdk', help=__doc__, description=__doc__)

    parser.set_defaults(func=cmd)
