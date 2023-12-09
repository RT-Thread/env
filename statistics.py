# -*- coding:utf-8 -*-
#
# File      : vars.py
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
# 2022-5-6      WuGenSheng      Add copyright information
#
import os
import uuid

import requests

from vars import Import

from cmds import *


def get_mac_address():
    mac=uuid.UUID(int = uuid.getnode()).hex[-12:]
    return ":".join([mac[e:e+2] for e in range(0,11,2)])


def Information_statistics():
    # get the .config file from env
    env_kconfig_path = os.path.join(os.getcwd(), 'tools', 'scripts', 'cmds')
    env_config_file = os.path.join(env_kconfig_path, '.config')

    mac_addr = get_mac_address()
    env_config_file = os.path.join(env_kconfig_path, '.config')

    if not os.path.isfile(env_config_file):
        try:
            response = requests.get('https://www.rt-thread.org/studio/statistics/api/envuse?userid='+str(mac_addr)+'&username='+str(mac_addr)+'&envversion=1.0&studioversion=2.0&ip=127.0.0.1')
            if response.status_code != 200:
                return
        except Exception as e:
            exit(0)
    elif os.path.isfile(env_config_file) and cmd_package.find_bool_macro_in_config(env_config_file, 'SYS_PKGS_NOT_USING_STATISTICS'):
        return True


if __name__ == '__main__':
    Information_statistics()
