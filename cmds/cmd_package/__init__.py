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
# 2018-05-28     SummerGift      Add copyright information
# 2018-12-28     Ernest Chen     Add package information and enjoy package maker
# 2019-01-07     SummerGift      The prompt supports utf-8 encoding
# 2020-04-08     SummerGift      Optimize program structure
#

import os
from .cmd_package_printenv import package_print_env, package_print_help
from .cmd_package_list import list_packages
from .cmd_package_wizard import package_wizard
from .cmd_package_update import package_update
from .cmd_package_upgrade import package_upgrade, package_upgrade_modules
from .cmd_package_utils import find_IAR_EXEC_PATH, find_MDK_EXEC_PATH

iar_exec_path = find_IAR_EXEC_PATH()
if iar_exec_path:
    os.environ['RTT_EXEC_PATH'] = iar_exec_path

mdk_exec_path = find_MDK_EXEC_PATH()
if mdk_exec_path:
    os.environ['RTT_EXEC_PATH'] = mdk_exec_path

def run_env_cmd(args):
    """Run packages command."""

    if args.package_update_force:
        package_update(True)
    elif args.package_update:
        package_update()
    elif args.package_create:
        package_wizard()
    elif args.list_packages:
        list_packages()
    elif args.package_upgrade:
        package_upgrade()
    elif args.package_upgrade_force:
        package_upgrade(force_upgrade=True)
    elif args.package_upgrade_script_force:
        package_upgrade(force_upgrade=True, upgrade_script=True)
    elif args.package_upgrade_modules:
        package_upgrade_modules()
    elif args.package_print_env:
        package_print_env()
    else:
        package_print_help()


def add_parser(sub):
    """The packages command parser for env."""

    parser = sub.add_parser('package', help=__doc__, description=__doc__)

    parser.add_argument('--update',
                        help='update packages, install or remove the packages by your settings in menuconfig',
                        action='store_true',
                        default=False,
                        dest='package_update')

    parser.add_argument('--update-force', '--force-update',
                        help='forcely update and clean packages, install or remove packages by settings in menuconfig',
                        action='store_true',
                        default=False,
                        dest='package_update_force')

    parser.add_argument('--list',
                        help='list target packages',
                        action='store_true',
                        default=False,
                        dest='list_packages')

    parser.add_argument('--wizard',
                        help='create a new package with wizard',
                        action='store_true',
                        default=False,
                        dest='package_create')

    parser.add_argument('--upgrade',
                        help='upgrade local packages index from git repository',
                        action='store_true',
                        default=False,
                        dest='package_upgrade')

    parser.add_argument('--upgrade-force', '--force-upgrade',
                        help='forcely upgrade local packages index from git repository',
                        action='store_true',
                        default=False,
                        dest='package_upgrade_force')

    parser.add_argument('--upgrade-script-force',
                        help='forcely upgrade local packages index and Env script from git repository',
                        action='store_true',
                        default=False,
                        dest='package_upgrade_script_force')

    parser.add_argument('--upgrade-modules',
                        help='upgrade python modules, e.g. requests module',
                        action='store_true',
                        default=False,
                        dest='package_upgrade_modules')

    parser.add_argument('--printenv',
                        help='print environmental variables to check',
                        action='store_true',
                        default=False,
                        dest='package_print_env')

    parser.set_defaults(func=run_env_cmd)
