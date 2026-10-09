# -*- coding:utf-8 -*-
#
# File      : cmd_menuconfig.py
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
# 2018-05-28     SummerGift      Add copyright information
# 2019-01-07     SummerGift      The prompt supports utf-8 encoding
# 2019-10-30     SummerGift      fix bug when generate some config item
#

import os
import platform
import sys
import subprocess

from config_file import find_setting, is_package_metadata, read_config, unquote, write_header
from env_paths import get_rtt_root as resolve_rtt_root
from vars import Import
from .cmd_package.cmd_package_utils import find_bool_macro_in_config, find_IAR_EXEC_PATH, find_MDK_EXEC_PATH


def get_rtt_root():
    return resolve_rtt_root(Import('bsp_root'))


def is_pkg_special_config(config_str):
    return is_package_metadata(config_str)


def _target_file(lines):
    return unquote(find_setting(lines, 'CONFIG_TARGET_FILE', '"rtconfig.h"')) or None


def get_target_file(filename):
    try:
        return _target_file(read_config(filename))
    except OSError:
        print('open config:%s failed' % filename)
        return None


def mk_rtconfig(filename):
    try:
        lines = read_config(filename)
    except OSError as e:
        print('Error message:%s' % e)
        print('open config:%s failed' % filename)
        return False

    target_fn = _target_file(lines)
    if target_fn:
        includes = ['rtconfig_project.h'] if os.path.isfile('rtconfig_project.h') else []
        write_header(lines, target_fn, 'RT_CONFIG_H__', includes)
    return True


# fix locale for kconfiglib
def kconfiglib_fix_locale():
    import locale

    # Get the list of supported locales
    supported_locales = set(locale.locale_alias.keys())

    # Check if LANG is set and its value is not in the supported locales
    if 'LANG' in os.environ and os.environ['LANG'] not in supported_locales:
        os.environ['LANG'] = 'C'

def cmd(args):
    env_root = Import('env_root')

    # Keep both legacy Kconfig symbol names and their environment variables set.
    rtt_root = get_rtt_root()
    if rtt_root:
        os.environ['RTT_ROOT'] = rtt_root
        os.environ['RTT_DIR'] = rtt_root

    if not os.path.exists('Kconfig'):
        if platform.system() == "Windows":
            os.system('chcp 65001  > nul')

        print(
            "\n\033[1;31;40m<menuconfig> 命令应当在某一特定 BSP 目录下执行，例如：\"rt-thread/bsp/stm32/stm32f091-st-nucleo\"\033[0m"
        )
        print("\033[1;31;40m请确保当前目录为 BSP 根目录，并且该目录中有 Kconfig 文件。\033[0m\n")

        print("<menuconfig> command should be used in a bsp root path with a Kconfig file.")
        print("Example: \"rt-thread/bsp/stm32/stm32f091-st-nucleo\"")
        print("You should check if there is a Kconfig file in your bsp root first.")

        if platform.system() == "Windows":
            os.system('chcp 437  > nul')

        return False

    if platform.system() == "Windows":
        os.system('chcp 437  > nul')

    # Env config, auto update packages and create mdk/iar project
    if args.menuconfig_setting:
        import kconfiglib
        import menuconfig

        env_kconfig_path = os.path.join(env_root, 'tools', 'scripts', 'cmds')
        beforepath = os.getcwd()
        os.chdir(env_kconfig_path)
        try:
            menuconfig.menuconfig(kconfiglib.Kconfig('Kconfig', suppress_traceback=True))
        finally:
            os.chdir(beforepath)
        return

    # generate rtconfig.h by .config.
    if args.menuconfig_g:
        print('generate rtconfig.h from .config')
        return mk_rtconfig(".config")

    if os.path.isfile(".config"):
        mtime = os.path.getmtime(".config")
    else:
        mtime = -1

    # Using the user specified configuration file
    if args.menuconfig_fn:
        print('use', args.menuconfig_fn)
        import shutil

        shutil.copy(args.menuconfig_fn, ".config")

    import kconfiglib

    if args.menuconfig_silent:
        kconf = kconfiglib.Kconfig('Kconfig', suppress_traceback=True)
        print(kconf.load_config('.config'))
        print(kconf.write_config())
    else:
        import menuconfig

        kconfiglib_fix_locale()
        menuconfig.menuconfig(kconfiglib.Kconfig('Kconfig', suppress_traceback=True))

    if os.path.isfile(".config"):
        mtime2 = os.path.getmtime(".config")
    else:
        mtime2 = -1

    # generate rtconfig.h by .config.
    if mtime != mtime2:
        if mk_rtconfig(".config") is False:
            return False

    # update pkgs
    env_kconfig_path = os.path.join(env_root, 'tools', 'scripts', 'cmds')
    fn = os.path.join(env_kconfig_path, '.config')

    if not os.path.isfile(fn):
        return

    if find_bool_macro_in_config(fn, 'SYS_AUTO_UPDATE_PKGS'):
        entry = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'env.py')
        returncode = subprocess.call([sys.executable, entry, 'pkg', '--update'])
        if returncode:
            return returncode
        print("==============================>The packages have been updated completely.")

    if platform.system() == "Windows":
        if find_bool_macro_in_config(fn, 'SYS_CREATE_MDK_IAR_PROJECT'):
            mdk_path = find_MDK_EXEC_PATH()
            iar_path = find_IAR_EXEC_PATH()

            for symbol, target, path in (
                ('SYS_CREATE_MDK4', 'mdk4', mdk_path),
                ('SYS_CREATE_MDK5', 'mdk5', mdk_path),
                ('SYS_CREATE_IAR', 'iar', iar_path),
            ):
                if find_bool_macro_in_config(fn, symbol):
                    command = ['scons', '--target=' + target, '-s']
                    if path:
                        command.append('--exec-path=' + path)
                    returncode = subprocess.call(command)
                    if returncode:
                        return returncode
                    print('Create %s project done' % target)
                    break


def add_parser(sub):
    parser = sub.add_parser(
        'menuconfig',
        help=__doc__,
        description=__doc__,
    )

    parser.add_argument(
        '--config',
        help='Using the user specified configuration file.',
        dest='menuconfig_fn',
    )

    parser.add_argument(
        '--generate',
        help='generate rtconfig.h by .config.',
        action='store_true',
        default=False,
        dest='menuconfig_g',
    )

    parser.add_argument(
        '--silent',
        help='Silent mode,don\'t display menuconfig window.',
        action='store_true',
        default=False,
        dest='menuconfig_silent',
    )

    parser.add_argument(
        '-s',
        '--setting',
        help='Env config,auto update packages and create mdk/iar project',
        action='store_true',
        default=False,
        dest='menuconfig_setting',
    )

    parser.set_defaults(func=cmd)
