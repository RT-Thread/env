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


if (__package__ or '').split('.', 1)[0] == 'env':
    from .config_file import iter_settings, read_config, unquote
else:
    from config_file import iter_settings, read_config, unquote


def _set_package_field(pkgs, name, field, value):
    for pkg in pkgs:
        if pkg.get('name') == name:
            pkg[field] = value
            return
    pkgs.append({'name': name, field: value})


def pkgs_path(pkgs, name, path):
    _set_package_field(pkgs, name, 'path', path)


def pkgs_ver(pkgs, name, ver):
    _set_package_field(pkgs, name, 'ver', ver)


def parse(filename):
    try:
        lines = read_config(filename)
    except OSError:
        print('open .config failed')
        return []

    packages = {}
    for key, value in iter_settings(lines):
        if not key.startswith('CONFIG_PKG_') or key.startswith('CONFIG_PKG_USING_'):
            continue
        name, separator, field = key[11:].rpartition('_')
        if separator and field in ('PATH', 'VER'):
            package = packages.setdefault(name, {'name': name})
            package['path' if field == 'PATH' else 'ver'] = unquote(value)
    return list(packages.values())
