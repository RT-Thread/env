# -*- coding:utf-8 -*-
#
# File      : cmd_package.py
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
# 2018-12-28     Ernest Chen     Add package information and enjoy package maker
# 2019-01-07     SummerGift      The prompt supports utf-8 encoding
# 2020-04-08     SummerGift      Optimize program structure
#

import os
import json
import kconfig
import pkgsdb
import shutil
import platform
import time
import archive
import sys
import requests
from package import Package, Bridge_SConscript
from vars import Import, Export
from .cmd_menuconfig import find_macro_in_config
from .cmd_package_list import list_packages
from .cmd_package_wizard import package_wizard
from .cmd_package_printenv import package_print_env
from .cmd_package_upgrade import package_upgrade
from .cmd_package_utils import get_url_from_mirror_server, execute_command, git_pull_repo


def determine_support_chinese(env_root):
    get_flag_file_path = os.path.join(env_root, 'tools', 'bin', 'env_above_ver_1_1')
    if os.path.isfile(get_flag_file_path):
        return True
    else:
        return False


def get_mirror_giturl(submod_name):
    """Gets the submodule's url on mirror server.

    Retrurn the download address of the submodule on the mirror server from the submod_name.
    """

    mirror_url = 'https://gitee.com/RT-Thread-Mirror/submod_' + submod_name + '.git'
    return mirror_url


def modify_submod_file_to_mirror(submod_path):
    """Modify the.gitmodules file based on the submodule to be updated"""

    replace_list = []
    try:
        with open(submod_path, 'r') as f:
            for line in f:
                line = line.replace('\t', '').replace(' ', '').replace('\n', '').replace('\r', '')
                if line.startswith('url'):
                    submod_git_url = line.split('=')[1]
                    submodule_name = submod_git_url.split('/')[-1].replace('.git', '')
                    replace_url = get_mirror_giturl(submodule_name)
                    # print(replace_url)
                    query_submodule_name = 'submod_' + submodule_name
                    # print(query_submodule_name)
                    get_package_url, get_ver_sha = get_url_from_mirror_server(
                        query_submodule_name, 'latest')

                    if get_package_url != None and determine_url_valid(get_package_url):
                        replace_list.append(
                            (submod_git_url, replace_url, submodule_name))

        with open(submod_path, 'r+') as f:
            submod_file_count = f.read()

        write_content = submod_file_count

        for item in replace_list:
            write_content = write_content.replace(item[0], item[1])

        with open(submod_path, 'w') as f:
            f.write(str(write_content))

        return replace_list

    except Exception as e:
        print('error message:%s\t' % e)


def determine_url_valid(url_from_srv):
    headers = {'Connection': 'keep-alive',
               'Accept-Encoding': 'gzip, deflate',
               'Accept': '*/*',
               'User-Agent': 'curl/7.54.0'}

    try:
        for i in range(0, 3):
            r = requests.get(url_from_srv, stream=True, headers=headers)
            if r.status_code == requests.codes.not_found:
                if i == 2:
                    print("Warning : %s is invalid." % url_from_srv)
                    return False
                time.sleep(1)
            else:
                break

        return True

    except Exception as e:
        print('error message:%s\t' % e)
        print('Network connection error or the url : %s is invalid.\n' % url_from_srv.encode("utf-8"))


def install_pkg(env_root, pkgs_root, bsp_root, pkg):
    """Install the required packages."""

    # default true
    ret = True
    local_pkgs_path = os.path.join(env_root, 'local_pkgs')
    bsp_pkgs_path = os.path.join(bsp_root, 'packages')

    # get the .config file from env
    env_kconfig_path = os.path.join(env_root, r'tools\scripts\cmds')
    env_config_file = os.path.join(env_kconfig_path, '.config')

    package = Package()
    pkg_path = pkg['path']
    if pkg_path[0] == '/' or pkg_path[0] == '\\':
        pkg_path = pkg_path[1:]
    pkg_path = os.path.join(pkgs_root, pkg_path, 'package.json')
    package.parse(pkg_path)

    url_from_json = package.get_url(pkg['ver'])
    package_url = package.get_url(pkg['ver'])
    pkgs_name_in_json = package.get_name()

    if package_url[-4:] == '.git':
        ver_sha = package.get_versha(pkg['ver'])

    # print("==================================================>")
    # print("packages name :"%pkgs_name_in_json.encode("utf-8"))
    # print("ver :"%pkg['ver']) 
    # print("url :"%package_url.encode("utf-8")) 
    # print("url_from_json : "%url_from_json.encode("utf-8"))
    # print("==================================================>")

    get_package_url = None
    get_ver_sha = None
    upstream_change_flag = False

    try:
        if (not os.path.isfile(env_config_file)) or \
                (os.path.isfile(env_config_file)
                 and find_macro_in_config(env_config_file, 'SYS_PKGS_DOWNLOAD_ACCELERATE')):
            get_package_url, get_ver_sha = get_url_from_mirror_server(pkgs_name_in_json, pkg['ver'])

            #  Check whether the package package url is valid
            if get_package_url is not None and determine_url_valid(get_package_url):
                package_url = get_package_url

                if get_ver_sha is not None:
                    ver_sha = get_ver_sha

                upstream_change_flag = True
    except Exception as e:
        print('error message:%s\t' % e)
        print("Failed to connect to the mirror server, package will be downloaded from non-mirror server.\n")

    if package_url[-4:] == '.git':
        try:
            repo_path = os.path.join(bsp_pkgs_path, pkgs_name_in_json)
            repo_path = repo_path + '-' + pkg['ver']
            repo_path_full = '"' + repo_path + '"'

            clone_cmd = 'git clone ' + package_url + ' ' + repo_path_full
            execute_command(clone_cmd, cwd=bsp_pkgs_path)

            git_check_cmd = 'git checkout -q ' + ver_sha
            execute_command(git_check_cmd, cwd=repo_path)
        except Exception as e:
            print("\nFailed to download software package with git. Please check the network connection.")
            return False

        if upstream_change_flag:
            cmd = 'git remote set-url origin ' + url_from_json
            execute_command(cmd, cwd=repo_path)

        # If there is a .gitmodules file in the package, prepare to update submodule.
        submodule_path = os.path.join(repo_path, '.gitmodules')
        if os.path.isfile(submodule_path):
            print("Start to update submodule")
            # print("开始更新软件包子模块")

            if (not os.path.isfile(env_config_file)) \
                    or (os.path.isfile(env_config_file)
                        and find_macro_in_config(env_config_file, 'SYS_PKGS_DOWNLOAD_ACCELERATE')):

                # print("开启了镜像加速，开始修改 .gitmodules 文件")
                replace_list = modify_submod_file_to_mirror(submodule_path)  # Modify .gitmodules file

            # print("开始执行更新动作")
            cmd = 'git submodule update --init --recursive'
            execute_command(cmd, cwd=repo_path)

            if (not os.path.isfile(env_config_file)) or \
                    (os.path.isfile(env_config_file) and
                     find_macro_in_config(env_config_file, 'SYS_PKGS_DOWNLOAD_ACCELERATE')):

                if len(replace_list):
                    for item in replace_list:
                        submod_dir_path = os.path.join(repo_path, item[2])
                        if os.path.isdir(submod_dir_path):
                            cmd = 'git remote set-url origin ' + item[0]
                            execute_command(cmd, cwd=submod_dir_path)

        if (not os.path.isfile(env_config_file)) or \
                (os.path.isfile(env_config_file)
                 and find_macro_in_config(env_config_file, 'SYS_PKGS_DOWNLOAD_ACCELERATE')):

            if os.path.isfile(submodule_path):
                cmd = 'git checkout .gitmodules'
                execute_command(cmd, cwd=repo_path)
    else:
        # Download a package of compressed package type.
        if not package.download(pkg['ver'], local_pkgs_path, package_url):
            return False

        pkg_dir = package.get_filename(pkg['ver'])
        pkg_dir = os.path.splitext(pkg_dir)[0]
        package_path = os.path.join(local_pkgs_path, package.get_filename(pkg['ver']))

        if not archive.packtest(package_path):
            print("package : %s is invalid" % package_path.encode("utf-8"))
            return False

        # unpack package
        if not os.path.exists(pkg_dir):

            try:
                if not package.unpack(package_path, bsp_pkgs_path, pkg, pkgs_name_in_json):
                    ret = False
            except Exception as e:
                os.remove(package_path)
                ret = False
                print('error message: %s\t' % e)
        else:
            print("The file does not exist.")
    return ret


def sub_list(aList, bList):
    """Return the items in aList but not in bList."""

    tmp = []
    for a in aList:
        if a not in bList:
            tmp.append(a)
    return tmp


def and_list(aList, bList):
    """Return the items in aList and in bList."""

    tmp = []
    for a in aList:
        if a in bList:
            tmp.append(a)
    return tmp


def update_submodule(repo_path):
    """Update the submodules in the repository."""

    submod_path = os.path.join(repo_path, '.gitmodules')
    if os.path.isfile(submod_path):
        print("Please wait a few seconds in order to update the submodule.")
        cmd = 'git submodule init -q'
        execute_command(cmd, cwd=repo_path)
        cmd = 'git submodule update'
        execute_command(cmd, cwd=repo_path)
        print("Submodule update successful")


def get_pkg_folder_by_orign_path(orign_path, version):
    # TODO fix for old version project, will remove after new major version
    # release
    if os.path.exists(orign_path + '-' + version):
        return orign_path + '-' + version
    return orign_path


def git_cmd_exec(cmd, cwd):
    try:
        execute_command(cmd, cwd=cwd)
    except Exception as e:
        print('error message:%s%s. %s \n\t' % (cwd.encode("utf-8"), " path doesn't exist", e))
        print("You can solve this problem by manually removing old packages and re-downloading them using env.")


def update_latest_packages(pkgs_fn, bsp_packages_path):
    """ update the packages that are latest version.

    If the selected package is the latest version,
    check to see if it is the latest version after the update command,
    if not, then update the latest version from the remote repository.
    If the download has a conflict, you are currently using the prompt
    message provided by git.
    """

    env_root = Import('env_root')
    pkgs_root = Import('pkgs_root')

    env_kconfig_path = os.path.join(env_root, r'tools\scripts\cmds')
    env_config_file = os.path.join(env_kconfig_path, '.config')

    with open(pkgs_fn, 'r') as f:
        read_back_pkgs_json = json.load(f)

    for pkg in read_back_pkgs_json:
        package = Package()
        pkg_path = pkg['path']
        if pkg_path[0] == '/' or pkg_path[0] == '\\':
            pkg_path = pkg_path[1:]

        pkg_path = os.path.join(pkgs_root, pkg_path, 'package.json')
        package.parse(pkg_path)
        pkgs_name_in_json = package.get_name()

        # Find out the packages which version is 'latest'
        if pkg['ver'] == "latest_version" or pkg['ver'] == "latest":
            repo_path = os.path.join(bsp_packages_path, pkgs_name_in_json)
            repo_path = get_pkg_folder_by_orign_path(repo_path, pkg['ver'])

            try:
                # If mirror acceleration is enabled, get the update address from
                # the mirror server.
                if (not os.path.isfile(env_config_file)) or \
                        (os.path.isfile(env_config_file)
                         and find_macro_in_config(env_config_file, 'SYS_PKGS_DOWNLOAD_ACCELERATE')):
                    payload_pkgs_name_in_json = pkgs_name_in_json.encode("utf-8")

                    # Change repo's upstream address.
                    mirror_url = get_url_from_mirror_server(
                        payload_pkgs_name_in_json, pkg['ver'])

                    if mirror_url[0] is not None:
                        cmd = 'git remote set-url origin ' + mirror_url[0]
                        git_cmd_exec(cmd, repo_path)

            except Exception as e:
                print("error message : %s" % e)
                print("Failed to connect to the mirror server, using non-mirror server to update.")

            # Update the package repository from upstream.
            git_pull_repo(repo_path)

            # If the package has submodules, update the submodules.
            update_submodule(repo_path)

            # recover origin url to the path which get from packages.json file
            if package.get_url(pkg['ver']):
                cmd = 'git remote set-url origin ' + \
                      package.get_url(pkg['ver'])
                git_cmd_exec(cmd, repo_path)
            else:
                print("Can't find the package : %s's url in file : %s" %
                      (payload_pkgs_name_in_json, pkg_path))

            print("==============================>  %s update done\n" % (pkgs_name_in_json))


def pre_package_update():
    """ Make preparations before updating the software package. """

    bsp_root = Import('bsp_root')
    env_root = Import('env_root')

    if not os.path.exists('.config'):
        if platform.system() == "Windows":
            os.system('chcp 65001  > nul')

        print("\n\033[1;31;40m当前路径下没有发现 .config 文件，请确保当前目录为 BSP 根目录。\033[0m")
        print("\033[1;31;40m如果确定当前目录为 BSP 根目录，请先使用 <menuconfig> 命令来生成 .config 文件。\033[0m\n")

        print('No system configuration file : .config.')
        print('You should use < menuconfig > command to config bsp first.')

        if platform.system() == "Windows":
            os.system('chcp 437  > nul')

        return False

    bsp_packages_path = os.path.join(bsp_root, 'packages')
    if not os.path.exists(bsp_packages_path):
        os.mkdir("packages")
        os.chdir(bsp_packages_path)
        fp = open("pkgs.json", 'w')
        fp.write("[]")
        fp.close()

        fp = open("pkgs_error.json", 'w')
        fp.write("[]")
        fp.close()
        os.chdir(bsp_root)

    # prepare target packages file
    dbsqlite_pathname = os.path.join(bsp_packages_path, 'packages.dbsqlite')
    Export('dbsqlite_pathname')
    dbsqlite_pathname = dbsqlite_pathname.encode('utf-8').decode('gbk')

    # Avoid creating tables more than one time
    if not os.path.isfile(dbsqlite_pathname):
        conn = pkgsdb.get_conn(dbsqlite_pathname)
        sql = '''CREATE TABLE packagefile
                    (pathname   TEXT  ,package  TEXT  ,md5  TEXT );'''
        pkgsdb.create_table(conn, sql)

    fn = '.config'
    pkgs = kconfig.parse(fn)

    # print("newpkgs", pkgs)

    newpkgs = pkgs

    if not os.path.exists(bsp_packages_path):
        os.mkdir(bsp_packages_path)

    pkgs_fn = os.path.join(bsp_packages_path, 'pkgs.json')

    # regenerate file : packages/pkgs.json 
    if not os.path.exists(pkgs_fn):
        os.chdir(bsp_packages_path)
        fp = open("pkgs.json", 'w')
        fp.write("[]")
        fp.close()
        os.chdir(bsp_root)

    # Reading data back from pkgs.json
    with open(pkgs_fn, 'r') as f:
        oldpkgs = json.load(f)

    # print("oldpkgs", oldpkgs)

    # regenerate file : packages/pkgs_error.json 
    pkgs_error_list_fn = os.path.join(bsp_packages_path, 'pkgs_error.json')

    if not os.path.exists(pkgs_error_list_fn):
        os.chdir(bsp_packages_path)
        fp = open("pkgs_error.json", 'w')
        fp.write("[]")
        fp.close()
        os.chdir(bsp_root)

    # Reading data back from pkgs_error.json
    with open(pkgs_error_list_fn, 'r') as f:
        pkgs_error = json.load(f)

    # create SConscript file
    if not os.path.isfile(os.path.join(bsp_packages_path, 'SConscript')):
        with open(os.path.join(bsp_packages_path, 'SConscript'), 'w') as f:
            f.write(str(Bridge_SConscript))

    return [oldpkgs, newpkgs, pkgs_error, pkgs_fn, pkgs_error_list_fn, bsp_packages_path, dbsqlite_pathname]


def error_packages_handle(error_packages_list, read_back_pkgs_json, pkgs_fn):
    bsp_root = Import('bsp_root')
    env_root = Import('env_root')
    pkgs_root = Import('pkgs_root')

    flag = None

    error_packages_redownload_error_list = []

    if len(error_packages_list):
        print("\n==============================> Packages list to download :  \n")
        for pkg in error_packages_list:
            print("Package name : %s, Ver : %s" % (pkg['name'].encode("utf-8"), pkg['ver'].encode("utf-8")))
        print("\nThe packages in the list above are accidentally deleted, env will redownload them.")
        print("Warning: Packages should be deleted in <menuconfig> command.\n")

        for pkg in error_packages_list:  # Redownloaded the packages in error_packages_list
            if install_pkg(env_root, pkgs_root, bsp_root, pkg):
                print("==============================> %s %s is redownloaded successfully. \n" % (
                    pkg['name'].encode("utf-8"), pkg['ver'].encode("utf-8")))
            else:
                error_packages_redownload_error_list.append(pkg)
                print(pkg, 'download failed.')
                flag = False

        if len(error_packages_redownload_error_list):
            print("%s" % error_packages_redownload_error_list)
            print("Packages:%s,%s redownloed error, you need to use <pkgs --update> command again to redownload them." %
                  (pkg['name'].encode("utf-8"), pkg['ver'].encode("utf-8")))
            write_back_pkgs_json = sub_list(
                read_back_pkgs_json, error_packages_redownload_error_list)
            read_back_pkgs_json = write_back_pkgs_json
            # print("write_back_pkgs_json:%s"%write_back_pkgs_json)
            pkgs_file = file(pkgs_fn, 'w')
            pkgs_file.write(json.dumps(write_back_pkgs_json, indent=1))
            pkgs_file.close()

    return flag


def rm_package(dir):
    if platform.system() != "Windows":
        shutil.rmtree(dir)
    else:
        dir = '"' + dir + '"'
        cmd = 'rd /s /q ' + dir
        os.system(cmd)

    if os.path.isdir(dir):
        if platform.system() != "Windows":
            shutil.rmtree(dir)
        else:
            dir = '"' + dir + '"'
            cmd = 'rmdir /s /q ' + dir
            os.system(cmd)

        if os.path.isdir(dir):
            print("Folder path: %s" % dir.encode("utf-8"))
            return False
    else:
        print("Path: %s \nSuccess: Folder has been removed. " % dir.encode("utf-8"))
        return True


def get_package_remove_path(pkg, bsp_packages_path):
    dirpath = pkg['path']
    ver = pkg['ver']
    if dirpath[0] == '/' or dirpath[0] == '\\':
        dirpath = dirpath[1:]

    if platform.system() == "Windows":
        dirpath = os.path.basename(dirpath.replace('/', '\\'))
    else:
        dirpath = os.path.basename(dirpath)

    removepath = os.path.join(bsp_packages_path, dirpath)

    # Handles the deletion of git repository folders with version Numbers
    removepath_ver = get_pkg_folder_by_orign_path(removepath, ver)
    return removepath_ver


def handle_download_error_packages(pkgs_fn, bsp_packages_path):
    """ handle download error packages.

    Check to see if the packages stored in the Json file list actually exist,
    and then download the packages if they don't exist.
    """

    with open(pkgs_fn, 'r') as f:
        read_back_pkgs_json = json.load(f)

    error_packages_list = []

    for pkg in read_back_pkgs_json:
        removepath = get_package_remove_path(pkg, bsp_packages_path)

        if os.path.exists(removepath):
            continue
        else:
            error_packages_list.append(pkg)

    # Handle the failed download packages
    get_flag = error_packages_handle(
        error_packages_list, read_back_pkgs_json, pkgs_fn)

    return get_flag


def write_storage_file(pkgs_fn, newpkgs):
    """Writes the updated configuration to pkgs.json file.

    Packages that are not downloaded correctly will be redownloaded at the
    next update.
    """

    with open(pkgs_fn, 'w') as f:
        f.write(str(json.dumps(newpkgs, indent=1)))


def package_update(isDeleteOld=False):
    """Update env's packages.

    Compare the old and new software package list and update the package.
    Remove unwanted packages and download the newly selected package.-
    Check if the files in the deleted packages have been changed, and if so, 
    remind the user saved the modified file.
    """

    sys_value = pre_package_update()

    if not sys_value:
        return

    bsp_root = Import('bsp_root')
    env_root = Import('env_root')
    pkgs_root = Import('pkgs_root')
    flag = True

    # According to the env version, whether Chinese output is supported or not
    if determine_support_chinese(env_root):
        if platform.system() == "Windows":
            os.system('chcp 65001 > nul')

    oldpkgs = sys_value[0]
    newpkgs = sys_value[1]
    pkgs_delete_error_list = sys_value[2]
    pkgs_fn = sys_value[3]
    pkgs_error_list_fn = sys_value[4]
    bsp_packages_path = sys_value[5]
    dbsqlite_pathname = sys_value[6]

    # print(oldpkgs)
    # print(newpkgs)

    if len(pkgs_delete_error_list):
        for error_package in pkgs_delete_error_list:
            removepath_ver = get_package_remove_path(
                error_package, bsp_packages_path)

            if os.path.isdir(removepath_ver):
                print("\nError: %s package delete failed, begin to remove it." %
                      error_package['name'].encode("utf-8"))

                if not rm_package(removepath_ver):
                    print("Error: Delete package %s failed! Please delete the folder manually.\n" %
                          error_package['name'].encode("utf-8"))
                    return

    # 1.in old ,not in new : Software packages that need to be removed.
    casedelete = sub_list(oldpkgs, newpkgs)
    pkgs_delete_fail_list = []

    for pkg in casedelete:

        removepath_ver = get_package_remove_path(pkg, bsp_packages_path)
        removepath_git = os.path.join(removepath_ver, '.git')

        # Delete. Git directory.
        if os.path.isdir(removepath_ver) and os.path.isdir(removepath_git):
            gitdir = removepath_ver

            print("\nStart to remove %s \nplease wait..." % gitdir.encode("utf-8"))
            if isDeleteOld:
                if rm_package(gitdir) == False:
                    print("Floder delete fail: %s" % gitdir.encode("utf-8"))
                    print("Please delete this folder manually.")
            else:
                print("The folder is managed by git. Do you want to delete this folder?\n")
                if sys.version_info < (3, 0):
                    rc = raw_input('Press the Y Key to delete the folder or just press Enter to keep it : ')
                else:
                    rc = input('Press the Y Key to delete the folder or just press Enter to keep it : ')

                if rc == 'y' or rc == 'Y':
                    try:
                        if rm_package(gitdir) == False:
                            pkgs_delete_fail_list.append(pkg)
                            print("Error: Please delete the folder manually.")
                    except Exception as e:
                        print('Error message:%s%s. error.message: %s\n\t' %
                              ("Delete folder failed: ", gitdir.encode("utf-8"), e))
        else:
            if os.path.isdir(removepath_ver):
                print("Start to remove %s \nplease wait..." % removepath_ver.encode("utf-8"))
                try:
                    pkgsdb.deletepackdir(removepath_ver, dbsqlite_pathname)
                except Exception as e:
                    pkgs_delete_fail_list.append(pkg)
                    print('Error message:\n%s %s. %s \n\t' % (
                        "Delete folder failed, please delete the folder manually", removepath_ver.encode("utf-8"), e))

    if len(pkgs_delete_fail_list):
        # write error messages
        pkgs_file = file(pkgs_error_list_fn, 'w')
        pkgs_file.write(json.dumps(pkgs_delete_fail_list, indent=1))
        pkgs_file.close()
        return
    else:
        # write error messages
        with open(pkgs_error_list_fn, 'w') as f:
            f.write(str(json.dumps(pkgs_delete_fail_list, indent=1)))

    # 2.in new not in old : Software packages to be installed.
    # If the package download fails, record it, and then download again when
    # the update command is executed.

    casedownload = sub_list(newpkgs, oldpkgs)
    # print 'in new not in old:', casedownload
    pkgs_download_fail_list = []

    for pkg in casedownload:
        if install_pkg(env_root, pkgs_root, bsp_root, pkg):
            print("==============================>  %s %s is downloaded successfully. \n" % (
                pkg['name'], pkg['ver']))
        else:
            # If the PKG download fails, record it in the
            # pkgs_download_fail_list.
            pkgs_download_fail_list.append(pkg)
            print(pkg, 'download failed.')
            flag = False

    # Get the currently updated configuration.
    newpkgs = sub_list(newpkgs, pkgs_download_fail_list)

    # Give hints based on the success of the download.
    if len(pkgs_download_fail_list):
        print("\nPackage download failed list:")
        for item in pkgs_download_fail_list:
            print(item)

        print("You need to reuse the <pkgs -update> command to download again.")

    # update pkgs.json and SConscript
    write_storage_file(pkgs_fn, newpkgs)

    # handle download error packages.
    get_flag = handle_download_error_packages(
        pkgs_fn, bsp_packages_path)

    if get_flag is not None:
        flag = get_flag

    # Update the software packages, which the version is 'latest'
    try:
        update_latest_packages(pkgs_fn, bsp_packages_path)
    except KeyboardInterrupt:
        flag = False

    if flag:
        print("Operation completed successfully.")
    else:
        print("Operation failed.")


def cmd(args):
    """Env's packages command execution options."""

    if args.package_update_y:
        package_update(True)
    elif args.package_update:
        package_update()
    elif args.package_create:
        package_wizard()
    elif args.list_packages:
        list_packages()
    elif args.package_upgrade:
        package_upgrade()
    elif args.package_print_env:
        package_print_env()
    else:
        os.system('pkgs -h')


def add_parser(sub):
    """The packages command parser for env."""

    parser = sub.add_parser('package', help=__doc__, description=__doc__)

    parser.add_argument('--force-update',
                        help='force update and clean packages, install or remove packages by settings in menuconfig',
                        action='store_true',
                        default=False,
                        dest='package_update_y')

    parser.add_argument('--update',
                        help='update packages, install or remove the packages by your settings in menuconfig',
                        action='store_true',
                        default=False,
                        dest='package_update')

    parser.add_argument('--list',
                        help='list target packages',
                        action='store_true',
                        default=False,
                        dest='list_packages')

    parser.add_argument('--wizard',
                        help='create a new package with wizard',
                        action='store_true',
                        default=False,
                        dest='package_create')

    parser.add_argument('--upgrade',
                        help='upgrade local packages list and ENV scripts from git repo',
                        action='store_true',
                        default=False,
                        dest='package_upgrade')

    parser.add_argument('--printenv',
                        help='print environmental variables to check',
                        action='store_true',
                        default=False,
                        dest='package_print_env')

    # parser.add_argument('--upgrade', dest='reposource', required=False,
    #            help='add source & update packages repo ')

    parser.set_defaults(func=cmd)
