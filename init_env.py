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


def run_proc(name, env_root):
    exec_file = os.path.join(env_root, r"tools\scripts\env.py")
    log_std = os.path.join(env_root, "env_log_std")
    log_err = os.path.join(env_root, "env_log_err")

    # noinspection PyBroadException
    try:
        os.system("python %s package --upgrade 1>%s 2>%s" % (exec_file, log_std, log_err))
    except Exception as e:
        print("Auto upgrade failed, please check your network.")
        pass


def main():
    env_root = env_root = os.getenv("ENV_ROOT")
    p = Process(target=run_proc, args=('upgrade', env_root))
    p.start()
    p.join()


if __name__ == '__main__':
    main()
