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
import re
import sys

from vars import Import
from .cmd_package.cmd_package_utils import find_bool_macro_in_config, find_IAR_EXEC_PATH, find_MDK_EXEC_PATH

def is_in_powershell():
    rst = False
    try:
        import psutil
        rst = bool(re.fullmatch('pwsh|pwsh.exe|powershell.exe', psutil.Process(os.getppid()).name()))
    except:
        pass

    return rst

def build_kconfig_frontends(rtt_root):
    kconfig_dir = os.path.join(rtt_root, 'tools', 'kconfig-frontends')
    os.system('scons -C ' + kconfig_dir)

def get_rtt_root():
    rtt_root = os.getenv("RTT_ROOT")
    if rtt_root is None:
        bsp_root = Import("bsp_root")
        if not os.path.exists(os.path.join(bsp_root, 'Kconfig')):
            return rtt_root
        with open(os.path.join(bsp_root, 'Kconfig')) as kconfig:
            lines = kconfig.readlines()
        for i in range(len(lines)):
            if "config RTT_DIR" in lines[i]:
                rtt_root = lines[i + 3].strip().split(" ")[1].strip('"')
                if not os.path.isabs(rtt_root):
                    rtt_root = os.path.join(bsp_root, rtt_root)
                break
    return rtt_root

def is_pkg_special_config(config_str):
    """judge if it's CONFIG_PKG_XX_PATH or CONFIG_PKG_XX_VER"""

    if isinstance(config_str, str):
        if config_str.startswith("PKG_") and (config_str.endswith('_PATH') or config_str.endswith('_VER')):
            return True
    return False

def get_target_file(filename):
    try:
        config = open(filename, "r")
    except:
        print('open config:%s failed' % filename)
        return None

    for line in config:
        line = line.lstrip(' ').replace('\n', '').replace('\r', '')

        if len(line) == 0: continue

        if line[0] == '#':
            continue
        else:
            setting = line.split('=')
            if len(setting) >= 2:
                if setting[0].startswith('CONFIG_TARGET_FILE'):
                    target_fn = re.findall(r"^.*?=(.*)$",line)[0]
                    if target_fn.startswith('"'):
                        target_fn = target_fn.replace('"', '')

                    if target_fn == '':
                        return None
                    else:
                        return target_fn

    return 'rtconfig.h'

def mk_rtconfig(filename):
    try:
        config = open(filename, 'r')
    except Exception as e:
        print('Error message:%s' % e)
        print('open config:%s failed' % filename)
        return

    target_fn = get_target_file(filename)
    if target_fn == None:
        return

    rtconfig = open(target_fn, 'w')
    rtconfig.write('#ifndef RT_CONFIG_H__\n')
    rtconfig.write('#define RT_CONFIG_H__\n\n')

    empty_line = 1

    for line in config:
        line = line.lstrip(' ').replace('\n', '').replace('\r', '')

        if len(line) == 0:
            continue

        if line[0] == '#':
            if len(line) == 1:
                if empty_line:
                    continue

                rtconfig.write('\n')
                empty_line = 1
                continue

            if line.startswith('# CONFIG_'):
                line = ' ' + line[9:]
            else:
                line = line[1:]
                rtconfig.write('/*%s */\n' % line)

            empty_line = 0
        else:
            empty_line = 0
            setting = line.split('=')
            if len(setting) >= 2:
                if setting[0].startswith('CONFIG_'):
                    setting[0] = setting[0][7:]

                # remove CONFIG_PKG_XX_PATH or CONFIG_PKG_XX_VER
                if is_pkg_special_config(setting[0]):
                    continue

                if setting[1] == 'y':
                    rtconfig.write('#define %s\n' % setting[0])
                else:
                    rtconfig.write('#define %s %s\n' % (setting[0], re.findall(r"^.*?=(.*)$", line)[0]))

    if os.path.isfile('rtconfig_project.h'):
        rtconfig.write('#include "rtconfig_project.h"\n')

    rtconfig.write('\n')
    rtconfig.write('#endif\n')
    rtconfig.close()


def cmd(args):
    import menuconfig
    import defconfig
    env_root = Import('env_root')

    # get RTT_DIR from environment or Kconfig file
    if get_rtt_root():
        os.environ['RTT_DIR'] = get_rtt_root()

    if not os.path.exists('Kconfig'):
        if platform.system() == "Windows":
            os.system('chcp 65001  > nul')

        print("\n\033[1;31;40m<menuconfig> 命令应当在某一特定 BSP 目录下执行，例如：\"rt-thread/bsp/stm32/stm32f091-st-nucleo\"\033[0m")
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
        env_kconfig_path = os.path.join(env_root, 'tools', 'scripts', 'cmds')
        beforepath = os.getcwd()
        os.chdir(env_kconfig_path)
        sys.argv = ['menuconfig', 'Kconfig']
        menuconfig._main()
        os.chdir(beforepath)
        return

    # generate rtconfig.h by .config.
    if args.menuconfig_g:
        print('generate rtconfig.h from .config')
        mk_rtconfig(".config")
        return


    if os.path.isfile(".config"):
        mtime = os.path.getmtime(".config")
    else:
        mtime = -1

    # Using the user specified configuration file
    if args.menuconfig_fn:
        print('use', args.menuconfig_fn)
        import shutil
        shutil.copy(args.menuconfig_fn, ".config")

    if args.menuconfig_silent:
        sys.argv = ['defconfig', '--kconfig=Kconfig', '.config']
        defconfig._main()
    else:
        sys.argv = ['menuconfig', 'Kconfig']
        menuconfig._main()

    if os.path.isfile(".config"):
        mtime2 = os.path.getmtime(".config")
    else:
        mtime2 = -1

    # generate rtconfig.h by .config.
    if mtime != mtime2:
        mk_rtconfig(".config")

    # update pkgs
    env_kconfig_path = os.path.join(env_root, 'tools', 'scripts', 'cmds')
    fn = os.path.join(env_kconfig_path, '.config')

    if not os.path.isfile(fn):
        return

    if find_bool_macro_in_config(fn, 'SYS_AUTO_UPDATE_PKGS'):
        if (is_in_powershell()):
            os.system('powershell pkgs.ps1 --update')
        else:
            os.system('pkgs --update')
        print("==============================>The packages have been updated completely.")

    if platform.system() == "Windows":
        if find_bool_macro_in_config(fn, 'SYS_CREATE_MDK_IAR_PROJECT'):
            mdk_path = find_MDK_EXEC_PATH()
            iar_path = find_IAR_EXEC_PATH()

            if find_bool_macro_in_config(fn, 'SYS_CREATE_MDK4'):
                if mdk_path:
                    os.system('scons --target=mdk4 -s --exec-path="' + mdk_path+'"')
                else:
                    os.system('scons --target=mdk4 -s')
                print("Create Keil-MDK4 project done")
            elif find_bool_macro_in_config(fn, 'SYS_CREATE_MDK5'):
                if mdk_path:
                    os.system('scons --target=mdk5 -s --exec-path="' + mdk_path+'"')
                else:
                     os.system('scons --target=mdk5 -s')
                print("Create Keil-MDK5 project done")
            elif find_bool_macro_in_config(fn, 'SYS_CREATE_IAR'):
                if iar_path:
                    os.system('scons --target=iar -s --exec-path="' + iar_path+'"')
                else:
                    os.system('scons --target=iar -s')
                print("Create IAR project done")


def add_parser(sub):
    parser = sub.add_parser('menuconfig', help=__doc__, description=__doc__)

    parser.add_argument('--config',
                        help='Using the user specified configuration file.',
                        dest='menuconfig_fn')

    parser.add_argument('--generate',
                        help='generate rtconfig.h by .config.',
                        action='store_true',
                        default=False,
                        dest='menuconfig_g')

    parser.add_argument('--silent',
                        help='Silent mode,don\'t display menuconfig window.',
                        action='store_true',
                        default=False,
                        dest='menuconfig_silent')

    parser.add_argument('-s', '--setting',
                        help='Env config,auto update packages and create mdk/iar project',
                        action='store_true',
                        default=False,
                        dest='menuconfig_setting')

    # parser.add_argument('--easy',
    #                     help='easy mode, place kconfig everywhere, modify the option env="RTT_ROOT" default "../.."',
    #                     action='store_true',
    #                     default=False,
    #                     dest='menuconfig_easy')

    parser.set_defaults(func=cmd)
