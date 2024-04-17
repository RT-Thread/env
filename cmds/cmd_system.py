# -*- coding:utf-8 -*-
#
# File      : cmd_system.py
# This file is part of RT-Thread RTOS
# COPYRIGHT (C) 2006 - 2018, RT-Thread Development Team
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
# 2018-5-28      SummerGift      Add copyright information
#

import os
from vars import Import

'''RT-Thread environment package system'''


def cmd(args):
    packages_root = Import('pkgs_root')

    if args.system_update:
        dir_list = os.listdir(packages_root)

        with open(os.path.join(packages_root, 'Kconfig'), 'w') as kconfig:
            for item in dir_list:
                if os.path.isfile(os.path.join(packages_root, item, 'Kconfig')):
                    kconfig.write('source "$PKGS_DIR/' + item + '/Kconfig"')
                    kconfig.write('\n')


def add_parser(sub):
    parser = sub.add_parser('system', help=__doc__, description=__doc__)

    parser.add_argument('--update',
                        help='update system menuconfig\'s online package options ',
                        action='store_true',
                        default=False,
                        dest='system_update')

    parser.set_defaults(func=cmd)
