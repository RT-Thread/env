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
# 2018-5-28      SummerGift      Add copyright information
#

import os
import json
import kconfig
import pkgsdb
import shutil
import platform
import requests
import subprocess
import time

from package import Package, Bridge_SConscript, Kconfig_file, Package_json_file, Sconscript_file
from vars import Import, Export
from string import Template
from cmd_menuconfig import find_macro_in_condfig

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
                print("Package was NOT found on mirror server.")
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
                    
            print("\nTips : \nThe system needs to be upgraded. \nPlease use the <pkgs --upgrade> command to upgrade packages index.\n")
            return None, None
        
    except Exception, e:
        print('e.message:%s\t' % e.message)
        print(
            "The server could not be contacted. Please check your network connection.")


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

    #print("==================================================>")
    #print "packages name:",pkgs_name_in_json
    #print "ver:",pkg['ver']
    #print "url:",package_url
    #print "url_from_json: ",url_from_json
    #print("==================================================>")
    
    get_package_url = None
    get_ver_sha     = None
    
    if os.path.isfile(env_config_file) and find_macro_in_condfig(env_config_file, 'SYS_PKGS_DOWNLOAD_ACCELERATE'):
        get_package_url, get_ver_sha = get_url_from_mirror_server(
            pkgs_name_in_json, pkg['ver'])

    if get_package_url != None:
        package_url = get_package_url
      
    if get_ver_sha != None:  
        ver_sha = get_ver_sha

    beforepath = os.getcwd()

    #print(package_url)

    if package_url[-4:] == '.git':
        repo_path = os.path.join(bsp_pkgs_path, pkgs_name_in_json)
        repo_path = repo_path + '-' + pkg['ver']
        cmd = 'git clone ' + package_url + ' ' + repo_path
        os.system(cmd)
        os.chdir(repo_path)
        cmd = 'git checkout -q ' + ver_sha
        os.system(cmd)

        # If there is a .gitmodules file in the package, prepare to update the
        # submodule.
        submod_path = os.path.join(repo_path, '.gitmodules')
        if os.path.isfile(submod_path):
            print("Start to update submodule")

            # Modify .gitmodules file
            replace_list = modify_submod_file_to_mirror(submod_path)

            cmd = 'git submodule init -q'
            os.system(cmd)
            cmd = 'git submodule update'
            if not os.system(cmd):
                print("Submodule update successful")

            if len(replace_list):
                for item in replace_list:
                    submod_dir_path = os.path.join(repo_path, item[2])
                    if os.path.isdir(submod_dir_path):
                        cmd = 'git remote set-url origin ' + item[0]
                        execute_command(cmd, cwd=submod_dir_path)

        cmd = 'git remote set-url origin ' + url_from_json
        os.system(cmd)

        cmd = 'git reset --hard origin/master'
        os.system(cmd)

        os.chdir(beforepath)
    else:
        # Download a package of compressed package type.
        if not package.download(pkg['ver'], local_pkgs_path, package_url):
            ret = False
            return ret

        pkg_dir = package.get_filename(pkg['ver'])
        pkg_dir = os.path.splitext(pkg_dir)[0]

        pkg_fullpath = os.path.join(
            local_pkgs_path, package.get_filename(pkg['ver']))
        #print("pkg_fullpath: %s"%pkg_fullpath)

        # unpack package
        if not os.path.exists(pkg_dir):
            package.unpack(pkg_fullpath, bsp_pkgs_path, pkg, pkgs_name_in_json)
            ret = True

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
        print ('no system configuration file : .config.')
        print ('you should use < menuconfig > command to config bsp first.')
        return

    #if not os.path.exists(target_pkgs_path):
    #    try:
    #        os.mkdir(target_pkgs_path)
    #    except:
    #        print 'mkdir packages directory failed'
    #        return

    pkgs = kconfig.parse(fn)

    #if not os.path.isfile(pkgs_fn):
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
        #print "package path:", pkg['path']

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
        cmd = 'git submodule init -q'
        execute_command(cmd, cwd=repo_path)
        cmd = 'git submodule update'
        if not os.system(cmd):
            print("Submodule update successful")
    

def get_pkg_folder_by_orign_path(orign_path, version):
    # TODO fix for old version project, will remove after new major version release
    if os.path.exists(orign_path + '-' + version):
        return orign_path + '-' + version
    return orign_path
    
def update_latest_packages(read_back_pkgs_json, bsp_packages_path):
    """ update the packages that are latest version.
    
    If the selected package is the latest version,
    check to see if it is the latest version after the update command,
    if not, then update the latest version from the remote repository.
    If the download has a conflict, you are currently using the prompt
    message provided by git.
    """

    env_root = Import('env_root')

    payload = {
        "userName": "RT-Thread",
        "packages": [
            {
                "name": "NULL",
            }
        ]
    }

    env_kconfig_path = os.path.join(env_root, 'tools\scripts\cmds')
    env_config_file = os.path.join(env_kconfig_path, '.config')

    beforepath = os.getcwd()
    for pkg in read_back_pkgs_json:
        package = Package()
        pkg_path = pkg['path']
        if pkg_path[0] == '/' or pkg_path[0] == '\\':
            pkg_path = pkg_path[1:]
        pkg_path = os.path.join(env_root, 'packages', pkg_path, 'package.json')
        package.parse(pkg_path)
        pkgs_name_in_json = package.get_name()
        if pkg['ver'] == "latest_version" or pkg['ver'] == "latest":
            repo_path = os.path.join(bsp_packages_path, pkgs_name_in_json)
            #ver_sha = package.get_versha(pkg['ver'])
            repo_path = get_pkg_folder_by_orign_path(repo_path, pkg['ver'])
            os.chdir(repo_path)

            if os.path.isfile(env_config_file) and find_macro_in_condfig(env_config_file, 'SYS_PKGS_DOWNLOAD_ACCELERATE'):
                payload_pkgs_name_in_json = pkgs_name_in_json.encode("utf-8")
                payload["packages"][0]['name'] = payload_pkgs_name_in_json

                try:
                    r = requests.post(
                        "http://packages.rt-thread.org/packages/queries", data=json.dumps(payload))
                    if r.status_code == requests.codes.ok:
                        #print("Software package get Successful")
                        package_info = json.loads(r.text)

                        if len(package_info['packages']) == 0:
                            print("Package was NOT found on mirror server.")
                        else:
                            for item in package_info['packages'][0]['packages_info']['site']:
                                if item['version'] == "latest_version" or item['version'] == "latest":
                                    # change origin url to the path which get
                                    # from mirror server
                                    cmd = 'git remote set-url origin ' + \
                                        item['URL']
                                    os.system(cmd)
                                    #print(cmd)
                except Exception, e:
                    print('e.message:%s\t' % e.message)
                    print(
                        "The server could not be contacted. Please check your network connection.")

            # Only one trace relationship can be used directly with git pull.
            cmd = 'git pull'
            os.system(cmd)

            # If the package has submodules, update the submodules.
            update_submodule(repo_path)

            # recover origin url to the path which get from packages.json file
            cmd = 'git remote set-url origin ' + package.get_url(pkg['ver'])
            os.system(cmd)
            os.chdir(beforepath)
            print("==============================>  %s update done \n" %
                  (pkgs_name_in_json))


def pre_package_update():

    bsp_root = Import('bsp_root')

    if not os.path.exists('.config'):
        print (
            "Can't find file .config.Maybe your working directory isn't in bsp root now.")
        print ("if your working directory isn't in bsp root now,please change your working directory to bsp root.")
        print ("if your working directory is in bsp root now, please use menuconfig command to create .config file first.")
        return

    bsp_packages_path = os.path.join(bsp_root, 'packages')
    if not os.path.exists(bsp_packages_path):
        os.mkdir("packages")
        os.chdir(bsp_packages_path)
        fp = open("pkgs.json", 'w')
        fp.write("[]")
        fp.close()
        os.chdir(bsp_root)

    # prepare target packages file
    dbsqlite_pathname = os.path.join(bsp_packages_path, 'packages.dbsqlite')
    Export('dbsqlite_pathname')

    # Avoid creating tables more than one time
    if not os.path.isfile(dbsqlite_pathname):
        conn = pkgsdb.get_conn(dbsqlite_pathname)
        sql = '''CREATE TABLE packagefile
                    (pathname   TEXT  ,package  TEXT  ,md5  TEXT );'''
        pkgsdb.create_table(conn, sql)

    fn = '.config'
    pkgs = kconfig.parse(fn)
    newpkgs = pkgs

    if not os.path.exists(bsp_packages_path):
        os.mkdir(bsp_packages_path)

    pkgs_fn = os.path.join(bsp_packages_path, 'pkgs.json')

    if not os.path.exists(pkgs_fn):
        print ("Maybe you delete the file pkgs.json by mistake.")
        print ("Do you want to create a new pkgs.json ?")
        rc = raw_input('Press the Y Key to create a new pkgs.json.')
        if rc == 'y' or rc == 'Y':
            os.chdir(bsp_packages_path)
            fp = open("pkgs.json", 'w')
            fp.write("[]")
            fp.close()
            os.chdir(bsp_root)
            print ("Create a new file pkgs.json done.")

    # Reading data back from pkgs.json
    with open(pkgs_fn, 'r') as f:
        oldpkgs = json.load(f)

    return [oldpkgs, newpkgs, pkgs_fn, bsp_packages_path, dbsqlite_pathname]


def package_update():
    """Update env's packages.

    Compare the old and new software package list and update the package.
    Remove unwanted packages and download the newly selected package.
    Check if the files in the deleted packages have been changed, and if so, 
    remind the user saved the modified file.
    """
    
    bsp_root = Import('bsp_root')
    env_root = Import('env_root')

    flag = True
    
    sys_value = pre_package_update()
    oldpkgs = sys_value[0]
    newpkgs = sys_value[1]
    pkgs_fn = sys_value[2]
    bsp_packages_path = sys_value[3]
    dbsqlite_pathname = sys_value[4]

    #print "newpkgs:",newpkgs
    #print "oldpkgs:",oldpkgs

    # 1.in old ,not in new
    casedelete = sub_list(oldpkgs, newpkgs)
    for pkg in casedelete:
        dirpath = pkg['path']
        ver = pkg['ver']
        if dirpath[0] == '/' or dirpath[0] == '\\':
            dirpath = dirpath[1:]
        dirpath = os.path.basename(dirpath.replace('/', '\\'))
        #print "basename:",os.path.basename(dirpath)
        removepath = os.path.join(bsp_packages_path, dirpath)

        # Handles the deletion of git repository folders with version Numbers
        git_removepath = get_pkg_folder_by_orign_path(removepath, ver)
        removepath_git = os.path.join(git_removepath, '.git')
        #print "floder to delete",removepath
        #print "removepath_git to delete",removepath_git
        
        # Delete. Git directory.

        if os.path.isdir(git_removepath) and os.path.isdir(removepath_git):
            gitdir = git_removepath

            print ("\nStart to remove %s, please wait...\n" % gitdir)
            print ("The folder is managed by git. Do you want to delete this folder?\n")

            rc = raw_input(
                'Press the Y Key to delete the folder or just press Enter to keep them :')
            if rc == 'y' or rc == 'Y':
                if platform.system() != "Windows":
                    shutil.rmtree(gitdir)
                else:
                    cmd = 'rd /s /q ' + gitdir
                    os.system(cmd)
                if os.path.isdir(gitdir):
                    if platform.system() != "Windows":
                        shutil.rmtree(gitdir)
                    else:
                        cmd = 'rmdir /s /q ' + gitdir
                        os.system(cmd)
                    print ("Delete not entirely,try again.")
                else:
                    print ("Folder has been removed.")
        else:
            removepath = get_pkg_folder_by_orign_path(removepath, ver)
            print("Start to remove %s, please wait...\n" % removepath)
            pkgsdb.deletepackdir(removepath, dbsqlite_pathname)

    # 2.in old and in new
    #caseinoperation = and_list(newpkgs,oldpkgs)

    # 3.in new not in old
    # If the package download fails, record it, and then download again when
    # the update command is executed.

    casedownload = sub_list(newpkgs, oldpkgs)
    #print 'in new not in old:',casedownload
    pkgs_list = []

    for pkg in casedownload:
        if install_pkg(env_root, bsp_root, pkg):
            print("==============================>  %s %s is downloaded successfully. \n" % (
                pkg['name'], pkg['ver']))
        else:
            # If the PKG download fails, record it in the pkgs_list.
            pkgs_list.append(pkg)
            print pkg, 'download failed.'
            flag = False

    # Get the currently updated configuration.
    newpkgs = sub_list(newpkgs, pkgs_list)

    # Give hints based on the success of the download.

    if len(pkgs_list):
        print("Package download failed pkgs_list: %s \n" % pkgs_list)
        print("You need to reuse the 'pkgs -update' command to download again.\n")

    # Writes the updated configuration to pkgs.json file.
    # Packages that are not downloaded correctly will be redownloaded at the
    # next update.

    pkgs_file = file(pkgs_fn, 'w')
    pkgs_file.write(json.dumps(newpkgs, indent=1))
    pkgs_file.close()

    # update SConscript file
    if not os.path.isfile(os.path.join(bsp_packages_path, 'SConscript')):
        bridge_script = file(os.path.join(
            bsp_packages_path, 'SConscript'), 'w')
        bridge_script.write(Bridge_SConscript)
        bridge_script.close()

    # Check to see if the packages stored in the Json file list actually exist,
    # and then download the packages if they don't exist.

    with open(pkgs_fn, 'r') as f:
        read_back_pkgs_json = json.load(f)

    #print(read_back_pkgs_json)

    error_packages_list = []
    error_packages_redownload_error_list = []
    for pkg in read_back_pkgs_json:
        dirpath = pkg['path']
        ver = pkg['ver']
        #print 'ver is :',ver[1:]
        if dirpath[0] == '/' or dirpath[0] == '\\':
            dirpath = dirpath[1:]

        dirpath = os.path.basename(dirpath)
        removepath = os.path.join(bsp_packages_path, dirpath)
        
        git_removepath = get_pkg_folder_by_orign_path(removepath, ver)
        #print "if floder exist",removepath
        removepath_ver = get_pkg_folder_by_orign_path(removepath, ver[1:])
        #print "if floder exist",removepath

        if os.path.exists(removepath):
            continue
        elif os.path.exists(removepath_ver):
            continue
        elif os.path.exists(git_removepath):
            continue   
        else:
            error_packages_list.append(pkg)

    if len(error_packages_list):
        print("\n==============================> Error packages list :  \n")
        for pkg in error_packages_list:
            print pkg['name'], pkg['ver']
        print("\nThe package in the list above is accidentally deleted.")
        print("Env will redownload packages that have been accidentally deleted.")
        print("If you really want to remove these packages, do that in the menuconfig command.\n")

        for pkg in error_packages_list:                # Redownloaded the packages in error_packages_list
            if install_pkg(env_root, bsp_root, pkg):
                print("==============================>  %s %s is redownloaded successfully. \n" % (
                    pkg['name'], pkg['ver']))
            else:
                error_packages_redownload_error_list.append(pkg)
                print pkg, 'download failed.'
                flag = False

        if len(error_packages_redownload_error_list):
            print("%s" % error_packages_redownload_error_list)
            print ("Packages:%s,%s redownloed error,you need to use 'pkgs --update' command again to redownload them." %
                   pkg['name'], pkg['ver'])
            write_back_pkgs_json = sub_list(
                read_back_pkgs_json, error_packages_redownload_error_list)
            read_back_pkgs_json = write_back_pkgs_json
            #print("write_back_pkgs_json:%s"%write_back_pkgs_json)
            pkgs_file = file(pkgs_fn, 'w')
            pkgs_file.write(json.dumps(write_back_pkgs_json, indent=1))
            pkgs_file.close()
    else:
        print("\nAll the selected packages have been downloaded successfully.\n")

    try:
        update_latest_packages(read_back_pkgs_json, bsp_packages_path)
    except KeyboardInterrupt:
        flag = 0

    if flag:
        print ("Operation completed successfully.")
    else:
        print ("Operation failed.")


def package_wizard():
    """Packages creation wizard.

    The user enters the package name, version number, category, and automatically generates the package index file.
    """

    print ('Welcome to package wizard,please enter the package information.')
    print ('The messages in [] is default setting.You can just press enter to use default Settings.')
    print ('Please enter the name of package:')
    name = raw_input()
    if name == '':
        print ('please provide the package name.\n')
        return

    default_description = 'a ' + name + ' package for rt-thread'
    #description = user_input('menuconfig option name,default:\n',default_description)
    description = default_description
    ver = user_input('version of package,default:\n', '1.0.0')
    ver_standard = ver.replace('.', '')
    #keyword = user_input('keyword,default:\n', name)
    keyword = name

    packageclass = ('iot', 'language', 'misc',
                    'multimedia', 'security', 'system')
    print ('Please choose a class for your packages.')
    print ('Enter 1 for iot and 2 for language, following the table below as a guideline.')
    print ("[1:iot]|[2:language]|[3:misc]|[4:multimedia]|[5:security]|[6:system]")

    classnu = raw_input()
    if classnu == '':
        print ('You must choose a class for your packages.Try again.\n')
        return

    if classnu >= '1' and classnu <= '6':
        pkgsclass = packageclass[int(classnu) - 1]
        #print pkgsclass
    else:
        print ('You must type in number 1 to 6.')
        return

    pkg_path = name
    if not os.path.exists(pkg_path):
        os.mkdir(pkg_path)
    else:
        print ("Warning: the package directory exits!")

    s = Template(Kconfig_file)
    uppername = str.upper(name)
    kconfig = s.substitute(name=uppername, description=description, version=ver,
                           pkgs_class=pkgsclass, lowercase_name=name, version_standard=ver_standard)
    f = file(os.path.join(pkg_path, 'Kconfig'), 'wb')
    f.write(kconfig)
    f.close()

    s = Template(Package_json_file)
    package = s.substitute(
        name=name, description=description, version=ver, keyword=keyword)
    f = file(os.path.join(pkg_path, 'package.json'), 'wb')
    f.write(package)
    f.close()

    s = Template(Sconscript_file)
    sconscript = s.substitute(name=name)
    f = file(os.path.join(pkg_path, 'SConscript'), 'wb')
    f.write(sconscript)
    f.close()

    print ('==============================> Your package index was made successfully.')


def upgrade_packages_index():
    """Update the package repository index."""
    
    packages_root = os.path.join(Import('env_root'), 'packages')
    git_repo = 'https://github.com/RT-Thread/packages.git'
    pkgs_path = os.path.join(packages_root, 'packages')

    if not os.path.isdir(pkgs_path):
        cmd = 'git clone ' + git_repo + ' ' + pkgs_path
        os.system(cmd)
        print ("upgrade from :%s" % (git_repo))
    
    for filename in os.listdir(packages_root):
        package_path = os.path.join(packages_root, filename)
        if os.path.isdir(package_path):
            if os.path.isdir(os.path.join(package_path, '.git')):
                cmd = r'git pull'
                execute_command(cmd, cwd=package_path)
                print("==============================>  Env %s update done \n" % filename)


def upgrade_env_script():
    """Update env function scripts."""
    
    env_scripts_root = os.path.join(Import('env_root'), 'tools', 'scripts')
    env_scripts_repo = 'https://github.com/RT-Thread/env.git'

    cmd = r'git pull -q' + env_scripts_repo
    execute_command(cmd, cwd=env_scripts_root)

    print("==============================>  Env scripts update done \n")


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

    if args.package_update:
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

    parser.add_argument('--update',
                        help='update packages, install or remove the packages as you set in menuconfig',
                        action='store_true',
                        default=False,
                        dest='package_update')

    parser.add_argument('--list',
                        help='list target packages',
                        action='store_true',
                        default=False,
                        dest='package_list')

    parser.add_argument('--wizard',
                        help='create a package with wizard',
                        action='store_true',
                        default=False,
                        dest='package_create')

    parser.add_argument('--upgrade',
                        help='update local packages list from git repo',
                        action='store_true',
                        default=False,
                        dest='package_upgrade')

    parser.add_argument('--printenv',
                        help='print environmental variables to check',
                        action='store_true',
                        default=False,
                        dest='package_print_env')

    #parser.add_argument('--upgrade', dest='reposource', required=False,
    #            help='add source & update packages repo ')

    parser.set_defaults(func=cmd)
