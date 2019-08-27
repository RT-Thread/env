# -*- coding:utf-8 -*-
#
# File      : env.py
# This file is part of RT-Thread RTOS
# COPYRIGHT (C) 2006 - 2019, RT-Thread Development Team
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
# 2019-8-26      SummerGift      first version
#

from multiprocessing import Process
import os
import time

def run_proc(name):
    exec_file = os.path.join(os.getcwd(), "tools\scripts\env.py")
    try:
        os.system("python %s package --upgrade 1>std_null 2>err_null"%exec_file)
    except Exception, e:
        print("Auto upgrade failed, please check your network.")
        pass

if __name__=='__main__':
    p = Process(target=run_proc, args=('upgrade',) )
    p.start()
    p.join()
