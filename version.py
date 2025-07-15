# -*- coding:utf-8 -*-
#
# File      : version.py
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
# 2025-06-23     Dongly      Add get_rt_env_version function

import json

def get_rt_env_version():
    rt_env_ver = None
    rt_env_name = None

    # try to read env.json to get information
    try:
        with open('env.json', 'r') as file:
            env_data = json.load(file)
            rt_env_name = env_data['name'] 
            rt_env_ver = env_data['version']
    except Exception as e:
        print("Failed to read env.json: %s" % str(e))

    if rt_env_name is None:
        rt_env_name = 'RT-Thread Env Tool'
    if rt_env_ver is None:
        # use the default 'v2.0.1'
        rt_env_ver = 'v2.0.1'
      
    return rt_env_name, rt_env_ver
