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

import platform
import subprocess
import time
import json
import sys
import requests


def execute_command(cmdstring, cwd=None, shell=True):
    """Execute the system command at the specified address."""

    if shell:
        cmdstring_list = cmdstring

    sub = subprocess.Popen(cmdstring_list, cwd=cwd, stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE, shell=shell, bufsize=4096)

    stdout_str = ''
    while sub.poll() is None:
        stdout_str += str(sub.stdout.read())
        time.sleep(0.1)

    return stdout_str


def git_pull_repo(repo_path, repo_url=''):
    if platform.system() == "Windows":
        cmd = r'git config --local core.autocrlf true'
        execute_command(cmd, cwd=repo_path)
    cmd = r'git pull ' + repo_url
    execute_command(cmd, cwd=repo_path)


def get_url_from_mirror_server(pkgs_name_in_json, pkgs_ver):
    """Get the download address from the mirror server based on the package name."""

    try:
        if type(pkgs_name_in_json) != type("str"):
            if sys.version_info < (3, 0):
                pkgs_name_in_json = str(pkgs_name_in_json)
            else:
                pkgs_name_in_json = str(pkgs_name_in_json)[2:-1]
    except Exception as e:
        print('error message:%s' % e)
        print("\nThe mirror server could not be contacted. Please check your network connection.")
        return None, None

    payload = {
        "userName": "RT-Thread",
        "packages": [
            {
                "name": "NULL",
            }
        ]
    }
    payload["packages"][0]['name'] = pkgs_name_in_json

    # print(payload)

    try:
        r = requests.post("http://packages.rt-thread.org/packages/queries", data=json.dumps(payload))

        if r.status_code == requests.codes.ok:
            package_info = json.loads(r.text)

            # Can't find package,change git package SHA if it's a git
            # package
            if len(package_info['packages']) == 0:
                print("Package was NOT found on mirror server. Using a non-mirrored address to download.")
                return None, None
            else:
                for item in package_info['packages'][0]['packages_info']['site']:
                    if item['version'] == pkgs_ver:
                        # Change download url
                        download_url = item['URL']
                        if download_url[-4:] == '.git':
                            # Change git package SHA
                            repo_sha = item['VER_SHA']
                            return download_url, repo_sha
                        return download_url, None

            print("\nTips : \nThe system needs to be upgraded.")
            print("Please use the <pkgs --upgrade> command to upgrade packages index.\n")
            return None, None

    except Exception as e:
        print('error message:%s' % e)
        print("\nThe mirror server could not be contacted. Please check your network connection.")
        return None, None
