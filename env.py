# -*- coding:utf-8 -*-
#
# File      : env.py
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
# 2019-1-16      SummerGift      Add chinese detection
#

import os
import sys
import argparse
import logging
import time
import platform

from cmds import *
from vars import Export

__version__ = 'rt-thread packages v1.2.0'


def init_argparse():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers()

    parser.add_argument('-v', '--version', action='version', version=__version__)

    cmd_system.add_parser(subs)
    cmd_menuconfig.add_parser(subs)
    cmd_package.add_parser(subs)

    return parser


def init_logger(env_root):
    localtime = time.asctime(time.localtime(time.time()))
    log_path = os.path.join(env_root, "env_logging", localtime.replace(" ", "-").replace(":", "-"))
    os.makedirs(log_path)
    log_name = os.path.join(log_path, "running_log.txt")

    log_format = "%(pathname)s %(lineno)d %(message)s "
    date_format = '%Y-%m-%d  %H:%M:%S %a '
    logging.basicConfig(level=logging.WARNING,
                        format=log_format,
                        datefmt=date_format,
                        # filename=log_name
                        )


def get_env_root():
    env_root = os.getenv("ENV_ROOT")
    if env_root is None:
        if platform.system() != 'Windows':
            env_root = os.path.join(os.getenv('HOME'), '.env')
        else:
            env_root = os.path.join(os.getenv('USERPROFILE'), '.env')

    return env_root


def get_package_root(env_root):
    package_root = os.getenv("PKGS_ROOT")
    if package_root is None:
        package_root = os.path.join(env_root, 'packages')
    return package_root


def get_bsp_root():
    bsp_root = os.getcwd()

    # noinspection PyBroadException
    try:
        bsp_root.encode('utf-8').decode("ascii")
    except Exception as e:
        if platform.system() == "Windows":
            os.system('chcp 65001  > nul')

        print("\n\033[1;31;40m警告：\033[0m")
        print("\033[1;31;40m当前路径不支持非英文字符，请修改当前路径为纯英文路径。\033[0m")
        print("\033[1;31;40mThe current path does not support non-English characters.\033[0m")
        print("\033[1;31;40mPlease modify the current path to a pure English path.\033[0m")

        if platform.system() == "Windows":
            os.system('chcp 437  > nul')

        exit(1)

    return bsp_root


def export_environment_variable():
    script_root = os.path.split(os.path.realpath(__file__))[0]
    sys.path = sys.path + [os.path.join(script_root)]
    bsp_root = get_bsp_root()
    env_root = get_env_root()
    pkgs_root = get_package_root(env_root)

    Export('env_root')
    Export('bsp_root')
    Export('pkgs_root')


def main():
    export_environment_variable()
    init_logger(get_env_root())

    parser = init_argparse()
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
