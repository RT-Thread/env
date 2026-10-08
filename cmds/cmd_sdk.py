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
import platform
from vars import Import, Export

'''RT-Thread environment sdk setting'''


def cmd(args):
    import kconfiglib
    import menuconfig
    from cmds.cmd_package import get_packages
    from cmds.cmd_package import package_update

    # change to sdk root directory
    tools_kconfig_path = os.path.join(Import('env_root'), 'tools', 'scripts')
    beforepath = os.getcwd()
    before_hostos = os.environ.get('HOSTOS')
    os.chdir(tools_kconfig_path)

    # set HOSTOS
    os.environ['HOSTOS'] = platform.system()

    # change bsp root to sdk root
    bsp_root = tools_kconfig_path
    before_bsp_root = Import('bsp_root')
    Export('bsp_root')

    try:
        menuconfig.menuconfig(kconfiglib.Kconfig('Kconfig', suppress_traceback=True))
        if package_update() is False:
            return False
        sdk_packages = [
            {'name': item['name'], 'path': item['name'] + '-' + item['ver']}
            for item in get_packages()
        ]
        with open(os.path.join(tools_kconfig_path, 'sdk_list.json'), 'w', encoding='utf-8') as f:
            json.dump(sdk_packages, f, ensure_ascii=False, indent=4)
        return True
    finally:
        os.chdir(beforepath)
        if before_hostos is None:
            os.environ.pop('HOSTOS', None)
        else:
            os.environ['HOSTOS'] = before_hostos
        bsp_root = before_bsp_root
        Export('bsp_root')


def add_parser(sub):
    parser = sub.add_parser('sdk', help=__doc__, description=__doc__)

    parser.set_defaults(func=cmd)
