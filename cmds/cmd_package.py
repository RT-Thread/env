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
#

import os
import json
import kconfig
import pkgsdb
import shutil
import platform
import subprocess
import time
import logging
import archive
import sys

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

from package import Package, Bridge_SConscript, Kconfig_file, Package_json_file, Sconscript_file
from vars import Import, Export
from string import Template
from cmd_menuconfig import find_macro_in_config


class Logger:
    def __init__(self, log_name, clevel=logging.DEBUG):
        self.logger = logging.getLogger(log_name)
        self.logger.setLevel(logging.DEBUG)
        fmt = logging.Formatter(
            '[%(levelname)s] %(message)s')

        # set cmd log
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        sh.setLevel(clevel)
        self.logger.addHandler(sh)

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def war(self, message):
        self.logger.warn(message)

    def error(self, message):
        self.logger.error(message)

    def cri(self, message):
        self.logger.critical(message)


"""package command"""

def execute_command(cmdstring, cwd=None, shell=True):
    """Execute the system command at the specified address."""

    if shell:
        cmdstring_list = cmdstring

    sub = subprocess.Popen(cmdstring_list, cwd=cwd, stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE, shell=shell, bufsize=4096)

    stdout_str = ''
    while sub.poll() is None:
        stdout_str += sub.stdout.read()
        time.sleep(0.1)

    return stdout_str


def user_input(msg, default_value):
    """Gets the user's keyboard input."""

    if default_value != '':
        msg = '%s[%s]' % (msg, default_value)

    print(msg)
    value = raw_input()
    if value == '':
        value = default_value

    return value


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

    except Exception, e:
        print('e.message:%s\t' % e.message)


def get_url_from_mirror_server(pkgs_name_in_json, pkgs_ver):
    """Get the download address from the mirror server based on the package name."""

    payload_pkgs_name_in_json = pkgs_name_in_json.encode("utf-8")
    payload = {
        "userName": "RT-Thread",
        "packages": [
            {
                "name": "NULL",
            }
        ]
    }
    payload["packages"][0]['name'] = payload_pkgs_name_in_json

    try:
        r = requests.post(
            "http://packages.rt-thread.org/packages/queries", data=json.dumps(payload))

        # print(r.status_code)

        if r.status_code == requests.codes.ok:
            package_info = json.loads(r.text)

            # print(package_info)

            # Can't find package,change git package SHA if it's a git
            # package
            if len(package_info['packages']) == 0:
                print(
                    "Package was NOT found on mirror server. Using a non-mirrored address to download.")
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

    except Exception, e:
        print('e.message:%s\t' % e.message)
        print("The server could not be contacted. Please check your network connection.")


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

    except Exception, e:
        #         print('e.message:%s\t' % e.message)
        print('Network connection error or the url : %s is invalid.\n' % url_from_srv)


def install_pkg(env_root, bsp_root, pkg):
    """Install the required packages."""

    # default true
    ret = True
    local_pkgs_path = os.path.join(env_root, 'local_pkgs')
    bsp_pkgs_path = os.path.join(bsp_root, 'packages')

    env_kconfig_path = os.path.join(env_root, 'tools\scripts\cmds')
    # get the .config file from env
    env_config_file = os.path.join(env_kconfig_path, '.config')

    package = Package()
    pkg_path = pkg['path']
    if pkg_path[0] == '/' or pkg_path[0] == '\\':
        pkg_path = pkg_path[1:]
    pkg_path = os.path.join(env_root, 'packages', pkg_path, 'package.json')
    package.parse(pkg_path)

    url_from_json = package.get_url(pkg['ver'])
    package_url = package.get_url(pkg['ver'])
    #package_name = pkg['name']
    pkgs_name_in_json = package.get_name()

    if package_url[-4:] == '.git':
        ver_sha = package.get_versha(pkg['ver'])

    # print("==================================================>")
    # print "packages name:",pkgs_name_in_json.encode("utf-8")
    # print "ver:",pkg['ver']
    # print "url:",package_url.encode("utf-8")
    # print "url_from_json: ",url_from_json.encode("utf-8")
    # print("==================================================>")

    get_package_url = None
    get_ver_sha = None
    upstream_change_flag = False

    if os.path.isfile(env_config_file) and find_macro_in_config(env_config_file, 'SYS_PKGS_DOWNLOAD_ACCELERATE'):
        get_package_url, get_ver_sha = get_url_from_mirror_server(pkgs_name_in_json, pkg['ver'])

        #  determine whether the package package url is valid
        if get_package_url != None and determine_url_valid(get_package_url):
            package_url = get_package_url

            if get_ver_sha != None:
                ver_sha = get_ver_sha

            upstream_change_flag = True

    if package_url[-4:] == '.git':

        repo_path = os.path.join(bsp_pkgs_path, pkgs_name_in_json)
        repo_path = repo_path + '-' + pkg['ver']
        repo_path_full = '"' + repo_path + '"'

        cmd = 'git clone ' + package_url + ' ' + repo_path_full
        execute_command(cmd, cwd=bsp_pkgs_path)

        cmd = 'git checkout -q ' + ver_sha
        execute_command(cmd, cwd=repo_path)

        if upstream_change_flag:
            cmd = 'git remote set-url origin ' + url_from_json
            execute_command(cmd, cwd=repo_path)

        # If there is a .gitmodules file in the package, prepare to update the
        # submodule.
        submod_path = os.path.join(repo_path, '.gitmodules')
        if os.path.isfile(submod_path):
            print("Start to update submodule")
            # print("开始更新软件包子模块")

            if os.path.isfile(env_config_file) and find_macro_in_config(env_config_file, 'SYS_PKGS_DOWNLOAD_ACCELERATE'):
                # print("开启了镜像加速，开始修改 .gitmodules 文件")
                replace_list = modify_submod_file_to_mirror(submod_path)  # Modify .gitmodules file

            # print("开始执行更新动作")
            cmd = 'git submodule update --init --recursive'
            execute_command(cmd, cwd=repo_path)

            if os.path.isfile(env_config_file) and find_macro_in_config(env_config_file, 'SYS_PKGS_DOWNLOAD_ACCELERATE'):
                if len(replace_list):
                    for item in replace_list:
                        submod_dir_path = os.path.join(repo_path, item[2])
                        if os.path.isdir(submod_dir_path):
                            cmd = 'git remote set-url origin ' + item[0]
                            execute_command(cmd, cwd=submod_dir_path)

        if os.path.isfile(env_config_file) and find_macro_in_config(env_config_file, 'SYS_PKGS_DOWNLOAD_ACCELERATE'):
            if os.path.isfile(submod_path):
                cmd = 'git checkout .gitmodules'
                execute_command(cmd, cwd=repo_path)

    else:
        # Download a package of compressed package type.
        if not package.download(pkg['ver'], local_pkgs_path.decode("gbk"), package_url):
            return False

        pkg_dir = package.get_filename(pkg['ver'])
        pkg_dir = os.path.splitext(pkg_dir)[0]
        pkg_fullpath = os.path.join(local_pkgs_path, package.get_filename(pkg['ver']))

        if not archive.packtest(pkg_fullpath.encode("gbk")):
            print("package : %s is invalid"%pkg_fullpath.encode("utf-8"))
            return False
     
        # unpack package
        if not os.path.exists(pkg_dir.encode("gbk")):

            try:
                if not package.unpack(pkg_fullpath.encode("gbk"), bsp_pkgs_path, pkg, pkgs_name_in_json.encode("gbk")):
                    ret = False
            except Exception, e:
                os.remove(pkg_fullpath)
                ret = False
                print('e.message: %s\t' % e.message)
        else:
            print("The file does not exist.")
    return ret


def package_list():
    """Print the packages list in env.

    Read the.config file in the BSP directory, 
    and list the version number of the selected package.
    """
    fn = '.config'
    env_root = Import('env_root')
#     bsp_root = Import('bsp_root')
#     target_pkgs_path = os.path.join(bsp_root, 'packages')
#     pkgs_fn = os.path.join(target_pkgs_path, 'pkgs.json')

    if not os.path.isfile(fn):
        print ('No system configuration file : .config.')
        print ('You should use < menuconfig > command to config bsp first.')
        return

    # if not os.path.exists(target_pkgs_path):
    #    try:
    #        os.mkdir(target_pkgs_path)
    #    except:
    #        print 'mkdir packages directory failed'
    #        return

    pkgs = kconfig.parse(fn)

    # if not os.path.isfile(pkgs_fn):
    #    pkgs_file = file(pkgs_fn, 'w')
    #    pkgs_file.write(json.dumps(pkgs, indent=1))
    #    pkgs_file.close()

    for pkg in pkgs:
        package = Package()
        pkg_path = pkg['path']
        if pkg_path[0] == '/' or pkg_path[0] == '\\':
            pkg_path = pkg_path[1:]

        #pkg_path = pkg_path.replace('/', '\\')
        pkg_path = os.path.join(env_root, 'packages', pkg_path, 'package.json')
        package.parse(pkg_path)

        pkgs_name_in_json = package.get_name()
        print pkgs_name_in_json, pkg['ver']
        # print "package path:", pkg['path']

    if not pkgs:
        print ("Packages list is empty.")
        print ('You can use < menuconfig > command to select online packages.')
        print ('Then use < pkgs --update > command to install them.')
    return


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
    except Exception, e:
        print('error message:%s%s. %s \nYou can solve this problem by manually removing old packages and re-downloading them using env.\t' %
              (cwd, " path doesn't exist", e.message))


def update_latest_packages(pkgs_fn, bsp_packages_path):
    """ update the packages that are latest version.

    If the selected package is the latest version,
    check to see if it is the latest version after the update command,
    if not, then update the latest version from the remote repository.
    If the download has a conflict, you are currently using the prompt
    message provided by git.
    """

    env_root = Import('env_root')

    env_kconfig_path = os.path.join(env_root, 'tools\scripts\cmds')
    env_config_file = os.path.join(env_kconfig_path, '.config')

    with open(pkgs_fn, 'r') as f:
        read_back_pkgs_json = json.load(f)

    for pkg in read_back_pkgs_json:
        package = Package()
        pkg_path = pkg['path']
        if pkg_path[0] == '/' or pkg_path[0] == '\\':
            pkg_path = pkg_path[1:]

        pkg_path = os.path.join(env_root, 'packages', pkg_path, 'package.json')
        package.parse(pkg_path)
        pkgs_name_in_json = package.get_name()

        # Find out the packages which version is 'latest'
        if pkg['ver'] == "latest_version" or pkg['ver'] == "latest":
            repo_path = os.path.join(bsp_packages_path, pkgs_name_in_json)
            repo_path = get_pkg_folder_by_orign_path(repo_path, pkg['ver'])

            # If mirror acceleration is enabled, get the update address from
            # the mirror server.
            if os.path.isfile(env_config_file) and find_macro_in_config(env_config_file, 'SYS_PKGS_DOWNLOAD_ACCELERATE'):
                payload_pkgs_name_in_json = pkgs_name_in_json.encode("utf-8")

                # Change repo's upstream address.
                mirror_url = get_url_from_mirror_server(
                    payload_pkgs_name_in_json, pkg['ver'])

                if mirror_url[0] != None:
                    cmd = 'git remote set-url origin ' + mirror_url[0]
                    git_cmd_exec(cmd, repo_path)

            # Update the package repository from upstream.
            cmd = 'git pull'
            git_cmd_exec(cmd, repo_path)

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

            print("==============================>  %s update done \n" %
                  (pkgs_name_in_json.encode("utf-8")))


def pre_package_update():

    bsp_root = Import('bsp_root')

    if not os.path.exists('.config'):
        print (
            "Can't find file .config.Maybe your working directory isn't in bsp root now.")
        print ("if your working directory isn't in bsp root now,please change your working directory to bsp root.")
        print ("if your working directory is in bsp root now, please use menuconfig command to create .config file first.")
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
    dbsqlite_pathname = dbsqlite_pathname.decode('gbk')
 
    # Avoid creating tables more than one time
    if not os.path.isfile(dbsqlite_pathname):
        conn = pkgsdb.get_conn(dbsqlite_pathname)
        sql = '''CREATE TABLE packagefile
                    (pathname   TEXT  ,package  TEXT  ,md5  TEXT );'''
        pkgsdb.create_table(conn, sql)
        print("Create dbsqlite done")

    fn = '.config'
    pkgs = kconfig.parse(fn)
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

    # regenerate file : packages/pkgs_error.json 
    pkgs_error_list_fn = os.path.join(
        bsp_packages_path, 'pkgs_error.json')

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
        bridge_script = file(os.path.join(
            bsp_packages_path, 'SConscript'), 'w')
        bridge_script.write(Bridge_SConscript)
        bridge_script.close()

    return [oldpkgs, newpkgs, pkgs_error, pkgs_fn, pkgs_error_list_fn, bsp_packages_path, dbsqlite_pathname]


def error_packages_handle(error_packages_list, read_back_pkgs_json, pkgs_fn):
    bsp_root = Import('bsp_root')
    env_root = Import('env_root')

    flag = None

    error_packages_redownload_error_list = []

    if len(error_packages_list):
        print("\n==============================> Packages list to download :  \n")
        for pkg in error_packages_list:
            print("Package name : %s, Ver : %s"%(pkg['name'].encode("utf-8"), pkg['ver'].encode("utf-8")))
        print("\nThe packages in the list above are accidentally deleted, env will redownload them.")
        print("Warning: Packages should be deleted in <menuconfig> command.\n")

        for pkg in error_packages_list:                # Redownloaded the packages in error_packages_list
            if install_pkg(env_root, bsp_root, pkg):
                print("==============================> %s %s is redownloaded successfully. \n" % (
                    pkg['name'].encode("utf-8"), pkg['ver'].encode("utf-8")))
            else:
                error_packages_redownload_error_list.append(pkg)
                print pkg, 'download failed.'
                flag = False

        if len(error_packages_redownload_error_list):
            print("%s" % error_packages_redownload_error_list)
            print ("Packages:%s,%s redownloed error, you need to use <pkgs --update> command again to redownload them." %
                   (pkg['name'], pkg['ver']))
            write_back_pkgs_json = sub_list(
                read_back_pkgs_json, error_packages_redownload_error_list)
            read_back_pkgs_json = write_back_pkgs_json
            # print("write_back_pkgs_json:%s"%write_back_pkgs_json)
            pkgs_file = file(pkgs_fn, 'w')
            pkgs_file.write(json.dumps(write_back_pkgs_json, indent=1))
            pkgs_file.close()
    else:
        print("\nAll the selected packages have been downloaded successfully.\n")

    return flag


def rm_package(dir):
    if platform.system() != "Windows":
        shutil.rmtree(dir)
    else:
        dir = '"' +  dir + '"'
        cmd = 'rd /s /q ' + dir
        os.system(cmd)

    if os.path.isdir(dir):
        if platform.system() != "Windows":
            shutil.rmtree(dir)
        else:
            dir = '"' +  dir + '"'
            cmd = 'rmdir /s /q ' + dir
            os.system(cmd)

        if os.path.isdir(dir):
            print ("Folder path: %s" % dir)
            return False
    else:
        print ("Path: %s \nSuccess: Folder has been removed. " % dir.encode("utf-8"))
        return True


def get_package_remove_path(pkg, bsp_packages_path):
    dirpath = pkg['path']
    ver = pkg['ver']
    if dirpath[0] == '/' or dirpath[0] == '\\':
        dirpath = dirpath[1:]
    dirpath = os.path.basename(dirpath.replace('/', '\\'))
    # print "basename:",os.path.basename(dirpath)
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

    pkgs_file = file(pkgs_fn, 'w')
    pkgs_file.write(json.dumps(newpkgs, indent=1))
    pkgs_file.close()


def package_update(isDeleteOld=False):
    """Update env's packages.

    Compare the old and new software package list and update the package.
    Remove unwanted packages and download the newly selected package.
    Check if the files in the deleted packages have been changed, and if so, 
    remind the user saved the modified file.
    """

    pkgs_update_log = Logger('pkgs_update', logging.WARNING)
    bsp_root = Import('bsp_root')
    env_root = Import('env_root')
    flag = True

    sys_value = pre_package_update()

    if not sys_value:
        return

    oldpkgs = sys_value[0]
    newpkgs = sys_value[1]
    pkgs_delete_error_list = sys_value[2]
    pkgs_fn = sys_value[3]
    pkgs_error_list_fn = sys_value[4]
    bsp_packages_path = sys_value[5]
    dbsqlite_pathname = sys_value[6]

    pkgs_update_log.info(
        '[Line: %d][Message : Begin to remove packages]' % sys._getframe().f_lineno)
    pkgs_update_log.info(
        '[Line: %d][Message : oldpkgs: %s ]' % (sys._getframe().f_lineno, oldpkgs))
    pkgs_update_log.info(
        '[Line: %d][Message : newpkgs: %s ]' % (sys._getframe().f_lineno, newpkgs))
    pkgs_update_log.info(
        '[Line: %d][Message : pkgs_delete_error_list: %s ]' % (sys._getframe().f_lineno, pkgs_delete_error_list))

    if len(pkgs_delete_error_list):
        for error_package in pkgs_delete_error_list:
            removepath_ver = get_package_remove_path(
                error_package, bsp_packages_path)

            if os.path.isdir(removepath_ver):
                print("\nError: %s package delete failed, begin to remove it."%
                      error_package['name'])

                if rm_package(removepath_ver) == False:
                    print("Error: Delete package %s failed! Please delete the folder manually.\n"%error_package['name'])
                    return

    # 1.in old ,not in new : Software packages that need to be removed.
    casedelete = sub_list(oldpkgs, newpkgs)
    pkgs_delete_fail_list = []

    for pkg in casedelete:

        removepath_ver = get_package_remove_path(pkg, bsp_packages_path)
        removepath_git = os.path.join(removepath_ver, '.git')

        # print "removepath_git to delete",removepath_git
        # Delete. Git directory.

        if os.path.isdir(removepath_ver) and os.path.isdir(removepath_git):
            gitdir = removepath_ver

            print ("\nStart to remove %s \nplease wait..." % gitdir.encode("utf-8"))
            if isDeleteOld:
                if rm_package(gitdir) == False:
                    print("Floder delete fail: %s" % gitdir)
                    print("Please delete this folder manually.")
            else:
                print (
                    "The folder is managed by git. Do you want to delete this folder?\n")
                rc = raw_input(
                    'Press the Y Key to delete the folder or just press Enter to keep it : ')
                if rc == 'y' or rc == 'Y':
                    try:
                        if rm_package(gitdir) == False:
                            pkgs_delete_fail_list.append(pkg)
                            print("Error: Please delete the folder manually.")
                    except Exception, e:
                        print('Error message:%s%s. error.message: %s\n\t' %
                              ("Delete folder failed: ", gitdir, e.message))
        else:
            if os.path.isdir(removepath_ver):
                print("Start to remove %s \nplease wait..." % removepath_ver.encode("utf-8"))
                try:
                    pkgsdb.deletepackdir(removepath_ver, dbsqlite_pathname)
                except Exception, e:
                    pkgs_delete_fail_list.append(pkg)
                    print('Error message:\n%s %s. %s \n\t' % (
                        "Delete folder failed, please delete the folder manually", removepath_ver, e.message))

    if len(pkgs_delete_fail_list):
#         print("Packages deletion failed list: %s \n" %
#               pkgs_delete_fail_list)

        # write error messages
        pkgs_file = file(pkgs_error_list_fn, 'w')
        pkgs_file.write(json.dumps(pkgs_delete_fail_list, indent=1))
        pkgs_file.close()

        return
    else:

        # write error messages
        pkgs_file = file(pkgs_error_list_fn, 'w')
        pkgs_file.write(json.dumps(pkgs_delete_fail_list, indent=1))
        pkgs_file.close()

    # 2.in new not in old : Software packages to be installed.
    # If the package download fails, record it, and then download again when
    # the update command is executed.

    pkgs_update_log.info(
        '[Line: %d][Message : Begin to download packages]' % sys._getframe().f_lineno)

    casedownload = sub_list(newpkgs, oldpkgs)
    # print 'in new not in old:', casedownload
    pkgs_download_fail_list = []

    for pkg in casedownload:
        if install_pkg(env_root, bsp_root, pkg):
            print("==============================>  %s %s is downloaded successfully. \n" % (
                pkg['name'], pkg['ver']))
        else:
            # If the PKG download fails, record it in the
            # pkgs_download_fail_list.
            pkgs_download_fail_list.append(pkg)
            print pkg, 'download failed.'
            flag = False

    pkgs_update_log.info(
        '[Line: %d][Message : Get the list of packages that have been updated]' % sys._getframe().f_lineno)

    # Get the currently updated configuration.
    newpkgs = sub_list(newpkgs, pkgs_download_fail_list)

    pkgs_update_log.info(
        '[Line: %d][Message : Print the list of software packages that failed to download]' % sys._getframe().f_lineno)
    # Give hints based on the success of the download.

    if len(pkgs_download_fail_list):
        print("Package download failed pkgs_download_fail_list: %s \n" %
              pkgs_download_fail_list)
        print("You need to reuse the <pkgs -update> command to download again.\n")

    # update pkgs.json and SConscript
    write_storage_file(pkgs_fn, newpkgs)

    # handle download error packages.
    get_flag = handle_download_error_packages(
        pkgs_fn, bsp_packages_path)

    if get_flag != None:
        flag = get_flag

    pkgs_update_log.info(
        '[Line: %d][Message : Begin to update latest version packages]' % sys._getframe().f_lineno)

    # Update the software packages, which the version is 'latest'
    try:
        update_latest_packages(pkgs_fn, bsp_packages_path)
    except KeyboardInterrupt:
        flag = False

    if flag:
        print ("Operation completed successfully.")
    else:
        print ("Operation failed.")
        
def package_wizard():
    """Packages creation wizard.

    The user enters the package name, version number, category, and automatically generates the package index file.
    """
    # Welcome
    print ('\033[4;32;40mWelcome to using package wizard, please follow below steps.\033[0m\n')
    
    #Simple introduction about the wizard
    print ('note :')
    print ('      \033[5;35;40m[   ]\033[0m means default setting or optional information.')
    print ('      \033[5;35;40mEnter\033[0m means using default option or ending and proceeding to the next step.') 
    
    #first step
    print ('\033[5;33;40m\n1.Please input a new package name :\033[0m')
    name = raw_input()
    while name == '' or name.isspace() == True :
        print ('\033[1;31;40mError: you must input a package name. Try again.\033[0m')
        name = raw_input()

    default_description = 'a ' + name + ' package for rt-thread'
    #description = user_input('menuconfig option name,default:\n',default_description)
    description = default_description
    
    #second step
    ver = user_input('\033[5;33;40m\n2.Please input this package version, default :\033[0m', '1.0.0')
    ver_standard = ver.replace('.', '')
    #keyword = user_input('keyword,default:\n', name)
    keyword = name

    #third step
    packageclass = ('iot', 'language', 'misc', 'multimedia',
                    'peripherals', 'security', 'system', 'tools')
    print ('\033[5;33;40m\n3.Please choose a package category from 1 to 8 : \033[0m')
    print ("\033[1;32;40m[1:iot]|[2:language]|[3:misc]|[4:multimedia]|[5:peripherals]|[6:security]|[7:system]|[8:tools]\033[0m")
    classnu = raw_input()
    while classnu == '' or classnu.isdigit()== False or int(classnu) < 1 or int(classnu) >8:
        if classnu == '' :
            print ('\033[1;31;40mError: You must choose a package category. Try again.\033[0m')
        else :    
            print ('\033[1;31;40mError: You must input an integer number from 1 to 8. Try again.\033[0m')
        classnu = raw_input()
     
    pkgsclass = packageclass[int(classnu) - 1]  
 
    
    #fourth step
    print ('\033[5;33;40m\n4.Please input author name of this package :\033[0m')        
    authorname = raw_input()
    while authorname == '':
        print ('\033[1;31;40mError: you must input author name of this package. Try again.\033[0m')
        authorname = raw_input()
    
    #fifth step    
    authoremail = raw_input('\033[5;33;40m\n5.Please input author email of this package :\n\033[0m') 
    while authoremail == '':
        print ('\033[1;31;40mError: you must input author email of this package. Try again.\033[0m')
        authoremail = raw_input()    
    
    #sixth step
    print ('\033[5;33;40m\n6.Please choose a license of this package from 1 to 4, or input other license name :\033[0m')
    print ("\033[1;32;40m[1:Apache-2.0]|[2:MIT]|[3:LGPL-2.1]|[4:GPL-2.0]\033[0m")       
    license_index = ('Apache-2.0', 'MIT', 'LGPL-2.1', 'GPL-2.0')
    license_class = raw_input()
    while license_class == '' :
        print ('\033[1;31;40mError: you must choose or input a license of this package. Try again.\033[0m')
        license_class = raw_input()  

    if license_class.isdigit()== True and int(license_class) >= 1 and int(license_class) <= 4:
        license = license_index[int(license_class) - 1]
    else :
        license = license_class   
        
    #seventh step       
    print ('\033[5;33;40m\n7.Please input the repository of this package :\033[0m') 
    print ("\033[1;32;40mFor example, hello package's repository url is 'https://github.com/RT-Thread-packages/hello'.\033[0m")
    
    repository = raw_input()
    while repository == '':
        print ('\033[1;31;40mError: you must input a repository of this package. Try again.\033[0m')
        repository = raw_input()         

    pkg_path = name
    if not os.path.exists(pkg_path):
        os.mkdir(pkg_path)
    else:
        print ("\033[1;31;40mError: the package directory is exits!\033[0m")

    s = Template(Kconfig_file)
    uppername = str.upper(name)
    kconfig = s.substitute(name=uppername, description=description, version=ver,
                           pkgs_class=pkgsclass, lowercase_name=name, version_standard=ver_standard)
    f = file(os.path.join(pkg_path, 'Kconfig'), 'wb')
    f.write(kconfig)
    f.close()

    s = Template(Package_json_file)
    package = s.substitute(name=name, pkgsclass=pkgsclass,authorname=authorname,authoremail=authoremail, description=description, version=ver, keyword=keyword,license=license, repository=repository)
    f = file(os.path.join(pkg_path, 'package.json'), 'wb')
    f.write(package)
    f.close()

    print ('\nThe package index has been created \033[1;32;40msuccessfully\033[0m.')
    print ('Please \033[5;34;40mupdate\033[0m other information of this package based on Kconfig and package.json in directory '+name+'.')

def upgrade_packages_index():
    """Update the package repository index."""
    
    env_root = Import('env_root')
    env_kconfig_path = os.path.join(env_root, 'tools\scripts\cmds')
    env_config_file = os.path.join(env_kconfig_path, '.config')
    if os.path.isfile(env_config_file) and find_macro_in_config(env_config_file, 'SYS_PKGS_DOWNLOAD_ACCELERATE'):
        get_package_url, get_ver_sha = get_url_from_mirror_server('packages', 'latest')
        if get_package_url != None:
            git_repo = get_package_url
        else:
            print("Failed to get url from mirror server. Using default url.")
            git_repo = 'https://gitee.com/RT-Thread-Mirror/packages.git'
    else:
        git_repo = 'https://github.com/RT-Thread/packages.git'
        
#     print(get_package_url,get_ver_sha)

    packages_root = os.path.join(env_root, 'packages')
    pkgs_path = os.path.join(packages_root, 'packages')

    if not os.path.isdir(pkgs_path):
        cmd = 'git clone ' + git_repo + ' ' + pkgs_path
        os.system(cmd)
        print ("upgrade from :%s" % (git_repo))
    else:
        print("Begin to upgrade env packages.")
        cmd = r'git pull ' + git_repo
        execute_command(cmd, cwd=pkgs_path)
        print("==============================>  Env packages upgrade done \n")

    for filename in os.listdir(packages_root):
        package_path = os.path.join(packages_root, filename)
        if os.path.isdir(package_path):

            if package_path == pkgs_path:
                continue

            if os.path.isdir(os.path.join(package_path, '.git')):
                print("Begin to upgrade %s." % filename)
                cmd = r'git pull'
                execute_command(cmd, cwd=package_path)
                print("==============================>  Env %s update done \n" % filename)


def upgrade_env_script():
    """Update env function scripts."""

    print("Begin to upgrade env scripts.")
    env_root = Import('env_root')
    env_kconfig_path = os.path.join(env_root, 'tools\scripts\cmds')
    env_config_file = os.path.join(env_kconfig_path, '.config')
    if os.path.isfile(env_config_file) and find_macro_in_config(env_config_file, 'SYS_PKGS_DOWNLOAD_ACCELERATE'):
        get_package_url, get_ver_sha = get_url_from_mirror_server('env', 'latest')
        if get_package_url != None:
            env_scripts_repo = get_package_url
        else:
            print("Failed to get url from mirror server. Using default url.")
            env_scripts_repo = 'https://gitee.com/RT-Thread-Mirror/env.git'
    else:
        env_scripts_repo = 'https://github.com/RT-Thread/env.git'

#     print(get_package_url,get_ver_sha)
    
    env_scripts_root = os.path.join(env_root, 'tools', 'scripts')
    cmd = r'git pull ' + env_scripts_repo
    execute_command(cmd, cwd=env_scripts_root)
    print("==============================>  Env scripts upgrade done \n")


def package_upgrade():
    """Update the package repository directory and env function scripts."""
    
    upgrade_packages_index()
    upgrade_env_script()


def package_print_env():
    print ("Here are some environmental variables.")
    print (
        "If you meet some problems,please check them. Make sure the configuration is correct.")
    print ("RTT_EXEC_PATH:%s" % (os.getenv("RTT_EXEC_PATH")))
    print ("RTT_CC:%s" % (os.getenv("RTT_CC")))
    print ("SCONS:%s" % (os.getenv("SCONS")))
    print ("PKGS_ROOT:%s" % (os.getenv("PKGS_ROOT")))

    env_root = os.getenv('ENV_ROOT')
    if env_root == None:
        if platform.system() != 'Windows':
            env_root = os.path.join(os.getenv('HOME'), '.env')

    print ("ENV_ROOT:%s" % (env_root))


def cmd(args):
    """Env's pkgs command execution options."""

    if args.package_update_y:
        package_update(True)
    elif args.package_update:
        package_update()
    elif args.package_create:
        package_wizard()
    elif args.package_list:
        package_list()
    elif args.package_upgrade:
        package_upgrade()
    elif args.package_print_env:
        package_print_env()
    else:
        os.system('pkgs -h')


def add_parser(sub):
    """The pkgs command parser for env."""

    parser = sub.add_parser('package', help=__doc__, description=__doc__)

    parser.add_argument('--force-update',
                        help='force update and clean packages, install or remove the packages by your settings in menuconfig',
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
                        dest='package_list')

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
