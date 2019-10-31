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
from vars import Import, Export


def is_pkg_special_config(config_str):
    ''' judge if it's CONFIG_PKG_XX_PATH or CONFIG_PKG_XX_VER'''

    if type(config_str) == type('a'):
        if config_str.startswith("PKG_") and (config_str.endswith('_PATH') or config_str.endswith('_VER')):
            return True
    return False


def mk_rtconfig(filename):
    try:
        config = open(filename, 'r')
    except:
        print('open config:%s failed' % filename)
        return

    rtconfig = open('rtconfig.h', 'w')
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
                    rtconfig.write('#define %s %s\n' % (setting[0], re.findall(r"^.*?=(.*)$",line)[0]))

    if os.path.isfile('rtconfig_project.h'):
        rtconfig.write('#include "rtconfig_project.h"\n')

    rtconfig.write('\n')
    rtconfig.write('#endif\n')
    rtconfig.close()


def find_macro_in_config(filename, macro_name):
    try:
        config = open(filename, "r")
    except:
        print('open .config failed')
        return

    empty_line = 1

    for line in config:
        line = line.lstrip(' ').replace('\n', '').replace('\r', '')

        if len(line) == 0:
            continue

        if line[0] == '#':
            if len(line) == 1:
                if empty_line:
                    continue

                empty_line = 1
                continue

            #comment_line = line[1:]
            if line.startswith('# CONFIG_'):
                line = ' ' + line[9:]
            else:
                line = line[1:]

            # print line

            empty_line = 0
        else:
            empty_line = 0
            setting = line.split('=')
            if len(setting) >= 2:
                if setting[0].startswith('CONFIG_'):
                    setting[0] = setting[0][7:]

                    if setting[0] == macro_name and setting[1] == 'y':
                        return True

    config.close()
    return False


def cmd(args):

    env_root = Import('env_root')
    os_version = platform.platform(True)[10:13]
    kconfig_win7_path = os.path.join(
        env_root, 'tools', 'bin', 'kconfig-mconf_win7.exe')

    if not os.path.exists('Kconfig'):
        if platform.system() == "Windows":
            os.system('chcp 65001  > nul')

        print("\n\033[1;31;40m<menuconfig> 命令应当在某一特定 BSP 目录下执行，例如：\"rt-thread/bsp/stm32/stm32f091-st-nucleo\"\033[0m")
        print("\033[1;31;40m请确保当前目录为 BSP 根目录，并且该目录中有 Kconfig 文件。\033[0m\n")

        print ("<menuconfig> command should be used in a bsp root path with a Kconfig file.")
        print ("Example: \"rt-thread/bsp/stm32/stm32f091-st-nucleo\"")
        print ("You should check if there is a Kconfig file in your bsp root first.")

        if platform.system() == "Windows":
            os.system('chcp 437  > nul')

        return False

    fn = '.config'

    if os.path.isfile(fn):
        mtime = os.path.getmtime(fn)
    else:
        mtime = -1

    if platform.system() == "Windows":
        os.system('chcp 437  > nul')

    if args.menuconfig_fn:
        print('use', args.menuconfig_fn)
        import shutil
        shutil.copy(args.menuconfig_fn, fn)
    elif args.menuconfig_g:
        mk_rtconfig(fn)
    elif args.menuconfig_silent:
        if float(os_version) >= 6.2:
            os.system('kconfig-mconf Kconfig -n')
            mk_rtconfig(fn)
        else:
            if os.path.isfile(kconfig_win7_path):
                os.system('kconfig-mconf_win7 Kconfig -n')
            else:
                os.system('kconfig-mconf Kconfig -n')

    elif args.menuconfig_setting:
        env_kconfig_path = os.path.join(env_root, 'tools\scripts\cmds')
        beforepath = os.getcwd()
        os.chdir(env_kconfig_path)

        if float(os_version) >= 6.2:
            os.system('kconfig-mconf Kconfig')
        else:
            if os.path.isfile(kconfig_win7_path):
                os.system('kconfig-mconf_win7 Kconfig')
            else:
                os.system('kconfig-mconf Kconfig')

        os.chdir(beforepath)

        return

    else:
        if float(os_version) >= 6.2:
            os.system('kconfig-mconf Kconfig')
        else:
            if os.path.isfile(kconfig_win7_path):
                os.system('kconfig-mconf_win7 Kconfig')
            else:
                os.system('kconfig-mconf Kconfig')

    if os.path.isfile(fn):
        mtime2 = os.path.getmtime(fn)
    else:
        mtime2 = -1

    if mtime != mtime2:
        mk_rtconfig(fn)

    if platform.system() == "Windows":
        env_kconfig_path = os.path.join(env_root, 'tools\scripts\cmds')
        fn = os.path.join(env_kconfig_path, '.config')

        if not os.path.isfile(fn):
            return

        if find_macro_in_config(fn, 'SYS_AUTO_UPDATE_PKGS'):
            os.system('pkgs --update')
            print("==============================>The packages have been updated completely.")

        if find_macro_in_config(fn, 'SYS_CREATE_MDK_IAR_PROJECT'):
            if find_macro_in_config(fn, 'SYS_CREATE_MDK4'):
                os.system('scons --target=mdk4 -s')
                print("Create mdk4 project done") 
            elif find_macro_in_config(fn, 'SYS_CREATE_MDK5'):
                os.system('scons --target=mdk5 -s')
                print("Create mdk5 project done") 
            elif find_macro_in_config(fn, 'SYS_CREATE_IAR'):
                os.system('scons --target=iar -s')
                print("Create iar project done") 


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

    parser.add_argument('--easy',
                        help='easy mode,place kconfig file everywhere,just modify the option env="RTT_ROOT" default "../.."',
                        action='store_true',
                        default=False,
                        dest='menuconfig_easy')

    parser.set_defaults(func=cmd)
