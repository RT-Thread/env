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

import json
import os
import platform
import shlex
import subprocess
import sys
import time
import shutil
import requests
import logging
from vars import Import


def get_git_root_path(repo_path):
    """Return the Git worktree root containing repo_path, if any."""
    if not repo_path or not os.path.isdir(repo_path):
        return None

    try:
        process = subprocess.Popen(
            ['git', '-C', os.path.abspath(repo_path), 'rev-parse', '--show-toplevel'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        output = process.communicate()[0]
        if process.returncode != 0:
            return None
        if not isinstance(output, str):
            output = output.decode('utf-8', errors='replace')
        return output.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def is_env_repository(repo_path):
    """Return True when repo_path resolves to the Env repository itself."""
    try:
        env_root = Import('env_root')
    except (KeyError, TypeError):
        env_root = None

    if not env_root:
        env_root = os.environ.get('ENV_ROOT')
    if not env_root:
        home = os.environ.get('HOME') or os.environ.get('USERPROFILE')
        if home:
            env_root = os.path.join(home, '.env')
    if not env_root:
        return False

    git_root = get_git_root_path(repo_path)
    if not git_root:
        return False

    git_root = os.path.realpath(git_root)
    env_root = os.path.realpath(env_root)
    env_repository_roots = (env_root, os.path.join(env_root, 'tools', 'scripts'))
    return any(git_root == root for root in map(os.path.realpath, env_repository_roots))


def _git_config_command_targets(command, cwd=None):
    """Yield working-tree paths for Git commands that may write config.

    Git global options can appear between ``git`` and the subcommand, and
    ``-C`` can select a repository unrelated to the process working directory.
    Tokenizing the command keeps the Env-repository guard effective for both
    forms instead of relying on a fragile substring match.
    """
    try:
        tokens = shlex.split(str(command), posix=(os.name != 'nt'))
    except ValueError:
        tokens = str(command).split()

    default_cwd = os.path.abspath(cwd or os.getcwd())
    config_commands = ('config', 'remote', 'submodule')

    for index, token in enumerate(tokens):
        if os.path.basename(token).lower() not in ('git', 'git.exe'):
            continue

        target_cwd = default_cwd
        git_dir = None
        cursor = index + 1
        while cursor < len(tokens):
            option = tokens[cursor]
            if option == '-C' and cursor + 1 < len(tokens):
                target_cwd = tokens[cursor + 1]
                cursor += 2
            elif option.startswith('-C') and len(option) > 2:
                target_cwd = option[2:]
                cursor += 1
            elif option == '--work-tree' and cursor + 1 < len(tokens):
                target_cwd = tokens[cursor + 1]
                cursor += 2
            elif option.startswith('--work-tree='):
                target_cwd = option.split('=', 1)[1]
                cursor += 1
            elif option == '--git-dir' and cursor + 1 < len(tokens):
                git_dir = tokens[cursor + 1]
                cursor += 2
            elif option.startswith('--git-dir='):
                git_dir = option.split('=', 1)[1]
                cursor += 1
            elif option in ('-c', '--config-env') and cursor + 1 < len(tokens):
                cursor += 2
            elif option.startswith('-'):
                cursor += 1
            else:
                break

        if cursor >= len(tokens) or tokens[cursor].lower() not in config_commands:
            continue

        target_cwd = target_cwd.strip()
        if len(target_cwd) >= 2 and target_cwd[0] == target_cwd[-1] and target_cwd[0] in ('"', "'"):
            target_cwd = target_cwd[1:-1]
        if not os.path.isabs(target_cwd):
            target_cwd = os.path.join(default_cwd, target_cwd)
        target_cwd = os.path.abspath(target_cwd)

        if git_dir:
            git_dir = git_dir.strip()
            if len(git_dir) >= 2 and git_dir[0] == git_dir[-1] and git_dir[0] in ('"', "'"):
                git_dir = git_dir[1:-1]
            if not os.path.isabs(git_dir):
                git_dir = os.path.join(target_cwd, git_dir)
            target_cwd = os.path.dirname(os.path.abspath(git_dir))
        yield target_cwd


def _changes_git_config(command):
    """Identify Git command families that can write repository config."""
    return any(_git_config_command_targets(command))


def execute_command(cmd_string, cwd=None, shell=True):
    """Execute the system command at the specified address."""

    for command_cwd in _git_config_command_targets(cmd_string, cwd):
        if is_env_repository(command_cwd):
            logging.warning('Refusing Git config mutation in the Env repository: %s', cmd_string)
            return ''

    logging.debug('execute_command: %s' % cmd_string)
    sub = subprocess.Popen(cmd_string, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=shell, bufsize=4096)

    stdout_str = ''
    while sub.poll() is None:
        stdout_str += str(sub.stdout.read())
        time.sleep(0.1)

    return stdout_str


def is_windows():
    if platform.system() == "Windows":
        return True
    else:
        return False


def git_pull_repo(repo_path, repo_url=''):
    try:
        if is_windows() and not is_env_repository(repo_path):
            cmd = r'git config --local core.autocrlf true'
            execute_command(cmd, cwd=repo_path)
        cmd = r'git pull ' + repo_url
        execute_command(cmd, cwd=repo_path)
    except Exception as e:
        print('Error message:%s' % e)


def get_url_from_mirror_server(package_name, package_version):
    """Get the download address from the mirror server based on the package name."""

    try:
        if type(package_name) == bytes:
            if sys.version_info < (3, 0):
                package_name = str(package_name)
            else:
                package_name = str(package_name, encoding='utf-8')
    except Exception as e:
        print('Error message:%s' % e)
        print("\nThe mirror server could not be contacted. Please check your network connection.")
        return None, None

    payload = {
        "userName": "RT-Thread",
        "packages": [
            {
                "name": "NULL",
            }
        ],
    }
    payload["packages"][0]['name'] = package_name

    try:
        r = requests.post("https://api.rt-thread.org/packages/queries", data=json.dumps(payload))

        if r.status_code == requests.codes.ok:
            package_info = json.loads(r.text)

            # Can't find package,change git package SHA if it's a git
            # package
            if len(package_info['packages']) == 0:
                print("Package was NOT found on mirror server. Using a non-mirrored address to download.")
                return None, None
            else:
                for item in package_info['packages'][0]['packages_info']['site']:
                    if item['version'] == package_version:
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
        print('Error message:%s' % e)
        print("\nThe mirror server could not be contacted. Please check your network connection.")
        return None, None


def user_input(msg=None):
    """Gets the union keyboard input."""

    if sys.version_info < (3, 0):
        if msg is not None:
            value = raw_input(msg)
        else:
            value = raw_input()
    else:
        if msg is not None:
            value = input(msg)
        else:
            value = input()

    return value


# Find the string after '='
# e.g CONFIG_SYS_AUTO_UPDATE_PKGS=y
# this function will return True and 'y'
# True means this macro has been set and y is the string after '='
def find_string_in_config(filename, macro_name):
    try:
        config = open(filename, "r")
    except Exception as e:
        print('Error message:%s' % e)
        print('open .config failed')
        return (False, None)

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

            # comment_line = line[1:]
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

                    if setting[0] == macro_name:
                        config.close()
                        return (True, setting[1])

    config.close()
    return (False, None)


# check if the bool macro is set or not
# e.g CONFIG_SYS_AUTO_UPDATE_PKGS=y
# will return True because this macro has been set
# If this macro cannot find or the .config cannot find or the macro is not set (n),
# the function will return False
def find_bool_macro_in_config(filename, macro_name):
    rst, str = find_string_in_config(filename, macro_name)
    if rst == True and str == 'y':
        return True
    else:
        return False


# find a string macro is defined or not
# e.g. CONFIG_SYS_CREATE_IAR_EXEC_PATH="C:/Program Files (x86)/IAR Systems/Embedded Workbench 8.3"
# will return "C:/Program Files (x86)/IAR Systems/Embedded Workbench 8.3"
# If this macro cannot find or .config cannot find
# the function will return None
def find_string_macro_in_config(filename, macro_name):
    rst, str = find_string_in_config(filename, macro_name)
    if rst == True:
        str = str.strip('"')
        return str
    else:
        return None


# return IAR execution path string or None for failure
def find_IAR_EXEC_PATH():
    env_root = Import('env_root')
    # get the .config file from env
    env_kconfig_path = os.path.join(env_root, 'tools', 'scripts', 'cmds')
    env_config_file = os.path.join(env_kconfig_path, '.config')

    return find_string_macro_in_config(env_config_file, 'SYS_CREATE_IAR_EXEC_PATH')


# return Keil-MDK execution path string or None for failure
def find_MDK_EXEC_PATH():
    env_root = Import('env_root')
    # get the .config file from env
    env_kconfig_path = os.path.join(env_root, 'tools', 'scripts', 'cmds')
    env_config_file = os.path.join(env_kconfig_path, '.config')

    return find_string_macro_in_config(env_config_file, 'SYS_CREATE_MDK_EXEC_PATH')


def remove_folder(folder_path):
    try:
        if os.path.isdir(folder_path):
            if is_windows():
                cmd = 'rd /s /q ' + folder_path
                os.system(cmd)
            else:
                shutil.rmtree(folder_path)
            return True
        else:
            return True
    except Exception as e:
        logging.warning('Error message : {0}'.format(e))
        return False
