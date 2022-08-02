# -*- coding:utf-8 -*-
#
# File      : cmd_package.py
# This file is part of RT-Thread RTOS
# COPYRIGHT (C) 2006 - 2020, RT-Thread Development Team
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
# 2020-04-08     SummerGift      Optimize program structure
#

import os
import uuid
from vars import Import
from .cmd_package_utils import git_pull_repo, get_url_from_mirror_server, find_macro_in_config
from .cmd_package_update import need_using_mirror_download

try:
    import requests
except ImportError:
    print("****************************************\n"
          "* Import requests module error.\n"
          "* Please install requests module first.\n"
          "* pip install step:\n"
          "* $ pip install requests\n"
          "* command install step:\n"
          "* $ sudo apt-get install python-requests\n"
          "****************************************\n")


def upgrade_packages_index(force_upgrade=False):
    """Update the package repository index."""

    env_root = Import('env_root')
    pkgs_root = Import('pkgs_root')
    env_kconfig_path = os.path.join(env_root, r'tools\scripts\cmds')
    env_config_file = os.path.join(env_kconfig_path, '.config')

    if need_using_mirror_download(env_config_file):
        get_package_url, get_ver_sha = get_url_from_mirror_server('packages', 'latest')

        if get_package_url is not None:
            git_repo = get_package_url
        else:
            print("Failed to get url from mirror server. Using default url.")
            git_repo = 'https://gitee.com/RT-Thread-Mirror/packages.git'
    else:
        git_repo = 'https://github.com/RT-Thread/packages.git'

    packages_root = pkgs_root
    pkgs_path = os.path.join(packages_root, 'packages')



    if not os.path.isdir(pkgs_path):
        cmd = 'git clone ' + git_repo + ' ' + pkgs_path
        os.system(cmd)
        print("upgrade from :%s" % (git_repo.encode("utf-8")))
    else:
        if force_upgrade:
            cwd = os.getcwd()
            os.chdir(pkgs_path)
            os.system('git fetch --all')
            os.system('git reset --hard origin/master')
            os.chdir(cwd)
        print("Begin to upgrade env packages.")
        git_pull_repo(pkgs_path, git_repo)
        print("==============================>  Env packages upgrade done \n")

    for filename in os.listdir(packages_root):
        package_path = os.path.join(packages_root, filename)
        if os.path.isdir(package_path):

            if package_path == pkgs_path:
                continue

            if os.path.isdir(os.path.join(package_path, '.git')):
                print("Begin to upgrade %s." % filename)
                git_pull_repo(package_path)
                print("==============================>  Env %s update done \n" % filename)


def upgrade_env_script():
    """Update env function scripts."""

    print("Begin to upgrade env scripts.")
    env_root = Import('env_root')
    env_kconfig_path = os.path.join(env_root, r'tools\scripts\cmds')
    env_config_file = os.path.join(env_kconfig_path, '.config')

    if need_using_mirror_download(env_config_file):
        get_package_url, get_ver_sha = get_url_from_mirror_server('env', 'latest')

        if get_package_url is not None:
            env_scripts_repo = get_package_url
        else:
            print("Failed to get url from mirror server. Using default url.")
            env_scripts_repo = 'https://gitee.com/RT-Thread-Mirror/env.git'
    else:
        env_scripts_repo = 'https://github.com/RT-Thread/env.git'

    env_scripts_root = os.path.join(env_root, 'tools', 'scripts')
    git_pull_repo(env_scripts_root, env_scripts_repo)
    print("==============================>  Env scripts upgrade done \n")

def get_mac_address():
    mac=uuid.UUID(int = uuid.getnode()).hex[-12:]
    return ":".join([mac[e:e+2] for e in range(0,11,2)])

def Information_statistics():

    env_root = Import('env_root')

    # get the .config file from env
    env_kconfig_path = os.path.join(env_root, 'tools\scripts\cmds')
    env_config_file = os.path.join(env_kconfig_path, '.config')

    mac_addr = get_mac_address()
    env_config_file = os.path.join(env_kconfig_path, '.config')
    if find_macro_in_config(env_config_file, 'SYS_PKGS_USING_STATISTICS'):
        response = requests.get('https://www.rt-thread.org/studio/statistics/api/envuse?userid='+str(mac_addr)+'&username='+str(mac_addr)+'&envversion=1.0&studioversion=2.0&ip=127.0.0.1')
        if response.status_code != 200:
            return
    else:
        return


def package_upgrade(force_upgrade=False):
    """Update the package repository directory and env function scripts."""

    if os.environ.get('RTTS_PLATFROM') != 'STUDIO':
        Information_statistics()

    upgrade_packages_index(force_upgrade=force_upgrade)
    upgrade_env_script()
