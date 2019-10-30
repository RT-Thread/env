# -*- coding:utf-8 -*-
#
# File      : kconfig.py
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


def pkgs_path(pkgs, name, path):
    for pkg in pkgs:
        if pkg.has_key('name') and pkg['name'] == name:
            pkg['path'] = path
            return

    pkg = {}
    pkg['name'] = name
    pkg['path'] = path
    pkgs.append(pkg)


def pkgs_ver(pkgs, name, ver):
    for pkg in pkgs:
        if pkg.has_key('name') and pkg['name'] == name:
            pkg['ver'] = ver
            return

    pkg = {}
    pkg['name'] = name
    pkg['ver'] = ver
    pkgs.append(pkg)


def parse(filename):
    ret = []
    try:
        config = file(filename)
    except:
        print('open .config failed') 
        return ret

    for line in config:
        line = line.lstrip(' ').replace('\n', '').replace('\r', '')

        if len(line) == 0:
            continue

        if line[0] == '#':
            continue
        else:
            setting = line.split('=', 1)
            if len(setting) >= 2:
                if setting[0].startswith('CONFIG_PKG_'):
                    pkg_prefix = setting[0][11:]

                    if pkg_prefix.startswith('USING_'):
                        pkg_name = pkg_prefix[6:]
                        # print 'enable package:', pkg_name
                    else:
                        if pkg_prefix.endswith('_PATH'):
                            pkg_name = pkg_prefix[:-5]
                            pkg_path = setting[1]
                            if pkg_path.startswith('"'):
                                pkg_path = pkg_path[1:]
                            if pkg_path.endswith('"'):
                                pkg_path = pkg_path[:-1]
                            pkgs_path(ret, pkg_name, pkg_path)

                        if pkg_prefix.endswith('_VER'):
                            pkg_name = pkg_prefix[:-4]
                            pkg_ver = setting[1]
                            if pkg_ver.startswith('"'):
                                pkg_ver = pkg_ver[1:]
                            if pkg_ver.endswith('"'):
                                pkg_ver = pkg_ver[:-1]
                            pkgs_ver(ret, pkg_name, pkg_ver)

    return ret


if __name__ == '__main__':
    parse('sample/.config')
