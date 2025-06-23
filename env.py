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
# 2020-4-13      SummerGift      refactoring
# 2025-1-27      bernard         Add env.json for env information

import os
import sys
import argparse
import logging
import platform
import json

script_path = os.path.abspath(__file__)
mpath = os.path.dirname(script_path)
sys.path.insert(0, mpath)

from cmds import *
from vars import Export
from version import get_rt_env_version

def show_version_warning():
    rtt_ver = get_rtt_verion()
    rt_env_name, rt_env_ver = get_rt_env_version()

    if rtt_ver <= (5, 1, 0) and rtt_ver != (0, 0, 0):
        print('===================================================================')
        print('Welcome to %s %s' % (rt_env_name, rt_env_ver))
        print('===================================================================')
        # print('')
        print('env v2.0 has made the following important changes:')
        print('1. Upgrading Python version from v2 to v3')
        print('2. Replacing kconfig-frontends with Python kconfiglib')
        print('')
        print(
            'env v2.0 require python kconfiglib (install by \033[4mpip install kconfiglib\033[0m),\n'
            'but env v1.5.x confilt with kconfiglib (please run \033[4mpip uninstall kconfiglib\033[0m)'
        )
        print('')
        print(
            '\033[1;31;40m** WARNING **\n'
            'env v2.0 only FULL SUPPORT RT-Thread > v5.1.0 or master branch.\n'
            'but you are working on RT-Thread V%d.%d.%d, please use env v1.5.x \033[0m' % rtt_ver,
        )
        print('===================================================================')


def init_argparse():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers()

    rt_env_name, rt_env_ver = get_rt_env_version()
    env_ver_str = '%s %s' % (rt_env_name, rt_env_ver)
    parser.add_argument('-v', '--version', action='version', version=env_ver_str)

    cmd_system.add_parser(subs)
    cmd_menuconfig.add_parser(subs)
    cmd_package.add_parser(subs)
    cmd_sdk.add_parser(subs)

    return parser


def init_logger(env_root):
    log_format = "%(module)s %(lineno)d %(levelname)s %(message)s \n"
    date_format = '%Y-%m-%d  %H:%M:%S %a '
    logging.basicConfig(
        level=logging.WARNING,
        format=log_format,
        datefmt=date_format,
        # filename=log_name
    )


def get_rtt_verion():
    import re

    rtt_root = get_rtt_root()

    if not rtt_root:
        return (0, 0, 0)

    if not os.path.isfile(os.path.join(rtt_root, "include", "rtdef.h")):
        return (0, 0, 0)

    major, minor, patch = 0, 0, 0
    with open(os.path.join(rtt_root, "include", 'rtdef.h')) as kconfig:
        lines = kconfig.readlines()
        for i in range(len(lines)):
            if "#define RT_VERSION_MAJOR" in lines[i]:
                major = int(re.split(r"\s+", lines[i].strip())[2])
            if "#define RT_VERSION_MINOR" in lines[i]:
                minor = int(re.split(r"\s+", lines[i].strip())[2])
            if "#define RT_VERSION_PATCH" in lines[i]:
                patch = int(re.split(r"\s+", lines[i].strip())[2])

    return (major, minor, patch)


def get_rtt_root():
    bsp_root = get_bsp_root()

    # bsp/kconfig文件获取rtt_root
    if os.path.isfile(os.path.join(bsp_root, "Kconfig")):
        with open(os.path.join(bsp_root, 'Kconfig')) as kconfig:
            lines = kconfig.readlines()
            for i in range(len(lines)):
                if "config RTT_DIR" in lines[i]:
                    rtt_root = lines[i + 3].strip().split(" ")[1].strip('"')
                    if not os.path.isabs(rtt_root):
                        rtt_root = os.path.join(bsp_root, rtt_root)
                    return os.path.normpath(rtt_root)
                if "RTT_DIR :=" in lines[i]:
                    rtt_root = lines[i].strip().split(":=")[1].strip()
                    if not os.path.isabs(rtt_root):
                        rtt_root = os.path.join(bsp_root, rtt_root)
                    return os.path.normpath(rtt_root)

    if os.path.isfile(os.path.join("rt-thread", "include", "rtdef.h")):
        return os.path.normpath(os.path.join(bsp_root, "rt-thread"))

    if "bsp" in bsp_root:
        rtt_root = bsp_root.split("bsp")[0]
        if os.path.isfile(os.path.join(rtt_root, "include", "rtdef.h")):
            return os.path.normpath(rtt_root)

    return None


def get_env_root():
    env_root = os.getenv("ENV_ROOT")
    if env_root is None:
        if platform.system() != 'Windows':
            env_root = os.path.join(os.getenv('HOME'), '.env')
        else:
            env_root = os.path.join(os.getenv('USERPROFILE'), '.env')
    return env_root


def get_package_root():
    package_root = os.getenv("PKGS_ROOT")
    if package_root is None:
        package_root = os.path.join(get_env_root(), 'packages')
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
    env_root = get_env_root()
    pkgs_root = get_package_root()
    bsp_root = get_bsp_root()

    os.environ["ENV_ROOT"] = env_root
    os.environ['PKGS_ROOT'] = pkgs_root
    os.environ['PKGS_DIR'] = pkgs_root
    os.environ['BSP_DIR'] = bsp_root

    Export('env_root')
    Export('pkgs_root')
    Export('bsp_root')


def exec_arg(arg):
    export_environment_variable()
    init_logger(get_env_root())

    sys.argv.insert(1, arg)

    parser = init_argparse()
    args = parser.parse_args()
    args.func(args)


def main():
    show_version_warning()
    export_environment_variable()
    init_logger(get_env_root())

    parser = init_argparse()
    args = parser.parse_args()

    if not vars(args):
        parser.print_help()
    else:
        args.func(args)


def menuconfig():
    show_version_warning()
    exec_arg('menuconfig')


def pkgs():
    show_version_warning()
    exec_arg('pkg')


def sdk():
    show_version_warning()
    exec_arg('sdk')


def system():
    show_version_warning()
    exec_arg('system')


if __name__ == '__main__':
    main()
