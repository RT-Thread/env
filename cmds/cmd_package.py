# -*- coding:utf-8 -*-
import argparse
import os
import json
import kconfig
import hashlib
import pkgsdb
import json
import shutil
import platform
import requests

from package import Package
from vars import Import, Export
from string import Template
from cmd_menuconfig import find_macro_in_condfig

'''package command'''

Bridge_SConscript = '''import os
from building import *

objs = []
cwd  = GetCurrentDir()
list = os.listdir(cwd)

for item in list:
    if os.path.isfile(os.path.join(cwd, item, 'SConscript')):
        objs = objs + SConscript(os.path.join(item, 'SConscript'))

Return('objs')
'''

""" 
Template for creating a new kconfig file
""" 
Kconfig_file = '''
# Kconfig file for package ${lowercase_name}
config PKG_USING_${name}
    bool "${description}"
    default n

if PKG_USING_${name}

    config PKG_${name}_PATH
        string
        default "/packages/${pkgs_class}/${lowercase_name}"

    choice
        prompt "${lowercase_name} version"
        help
            Select the ${lowercase_name} version

        config PKG_USING_${name}_V${version_standard}
            bool "v${version}"

        config PKG_USING_${name}_LATEST_VERSION
            bool "latest"
    endchoice
          
    config PKG_${name}_VER
       string
       default "v${version}"    if PKG_USING_${name}_V${version_standard}
       default "latest"    if PKG_USING_${name}_LATEST_VERSION

endif

'''

Package_json_file = '''
{
    "name": "${name}",
    "description": "${description}",
    "keywords": [
        "${keyword}"
    ],
    "site" : [
    {"version" : "v${version}", "URL" : "https://${name}-${version}.zip", "filename" : "${name}-${version}.zip","VER_SHA" : "fill in the git version SHA value"},
    {"version" : "latest", "URL" : "https://xxxxx.git", "filename" : "Null for git package","VER_SHA" : "fill in latest version branch name,such as mater"}
    ]
}
'''

Sconscript_file = '''
from building import *

cwd     = GetCurrentDir()
src     = Glob('*.c') + Glob('*.cpp')
CPPPATH = [cwd]

group = DefineGroup('${name}', src, depend = [''], CPPPATH = CPPPATH)

Return('group')
'''

def user_input(msg, default_value):

    if default_value != '': 
        msg = '%s[%s]' % (msg, default_value)
    
    print msg,
    value = raw_input()
    if value == '' : value = default_value

    return value

def install_pkg(env_root, bsp_root, pkg):
    ret = True
    local_pkgs_path = os.path.join(env_root, 'local_pkgs')
    bsp_pkgs_path = os.path.join(bsp_root, 'packages')

    env_kconfig_path = os.path.join(env_root, 'tools\scripts\cmds')
    env_config_file = os.path.join(env_kconfig_path,'.config')

    package = Package()
    pkg_path = pkg['path']
    if pkg_path[0] == '/' or pkg_path[0] == '\\': pkg_path = pkg_path[1:]
    pkg_path = os.path.join(env_root, 'packages', pkg_path, 'package.json')
    package.parse(pkg_path)

    url_from_json = package.get_url(pkg['ver'])
    package_url = package.get_url(pkg['ver'])
    package_name = pkg['name']
    pkgs_name_in_json =  package.get_name()

    if package_url[-4:] == '.git':
        ver_sha = package.get_versha(pkg['ver'])

    #print("==================================================>")
    #print "packages name:",pkgs_name_in_json
    #print "ver:",pkg['ver']
    #print "url:",package_url
    #print "url_from_json: ",url_from_json
    #print("==================================================>")

    if os.path.isfile(env_config_file) and find_macro_in_condfig(env_config_file,'SYS_PKGS_DOWNLOAD_ACCELERATE'):
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
            r = requests.post("http://packages.rt-thread.org/packages/queries", data=json.dumps(payload))
            #print(r.status_code)

            if r.status_code == requests.codes.ok:
                #print("Software package get Successful")
                package_info = json.loads(r.text)

                if len(package_info['packages']) == 0:                      # Can't find package,change git package SHA if it's a git package
                    #print("No packages were found in the mirror server.")
                else:
                    for item in package_info['packages'][0]['packages_info']['site']:
                        if item['version'] == pkg['ver']:
                            download_url = item['URL']
                            package_url = download_url                      # Change download url
                            #print("download_url from server: %s"%download_url)
                            if download_url[-4:] == '.git':
                                repo_sha = item['VER_SHA']
                                ver_sha = repo_sha                          # Change git package SHA
                                #print(repo_sha)
                            break
        except Exception, e:
            print("The server could not be contacted. Please check your network connection.")

    beforepath = os.getcwd()

    #print(package_url)

    if package_url[-4:] == '.git':
        repo_path = os.path.join(bsp_pkgs_path,pkgs_name_in_json)
        cmd = 'git clone '+ package_url + ' '+ repo_path
        #print(cmd)
        os.system(cmd)
        os.chdir(repo_path)
        cmd = 'git checkout '+ ver_sha
        os.system(cmd)
        cmd = 'git submodule init '
        os.system(cmd)
        cmd = 'git submodule update '
        if not os.system(cmd):
            print("Submodule update success")
        cmd = 'git remote set-url origin ' + url_from_json
        #print(cmd)
        os.system(cmd)
        os.chdir(beforepath)
    else:
        # download package
        if not package.download(pkg['ver'], local_pkgs_path, package_url):
            ret = False
            return ret

        pkg_dir = package.get_filename(pkg['ver'])
        pkg_dir = os.path.splitext(pkg_dir)[0]

        pkg_fullpath = os.path.join(local_pkgs_path, package.get_filename(pkg['ver']))
        #print("pkg_fullpath: %s"%pkg_fullpath)

        # unpack package
        if not os.path.exists(pkg_dir):
            package.unpack(pkg_fullpath, bsp_pkgs_path)
            ret = True

    return ret

def package_list():
    """Print the packages list in env.

    Read the.config file in the BSP directory, 
    and list the version number of the selected package.

    Args:
        none

    Returns:
        none

    Raises:
        none
    """
    fn = '.config'
    env_root = Import('env_root')
    bsp_root = Import('bsp_root')
    target_pkgs_path = os.path.join(bsp_root, 'packages')
    pkgs_fn = os.path.join(target_pkgs_path, 'pkgs.json')

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
        if pkg_path[0] == '/' or pkg_path[0] == '\\': pkg_path = pkg_path[1:]

        #pkg_path = pkg_path.replace('/', '\\')
        pkg_path = os.path.join(env_root, 'packages', pkg_path, 'package.json')
        package.parse(pkg_path)

        pkgs_name_in_json =  package.get_name()
        print pkgs_name_in_json, pkg['ver']
        #print "package path:", pkg['path']

    if not pkgs:
        print ("Packages list is empty.")
        print ('You can use < menuconfig > command to select online packages.')
        print ('Then use < pkgs --update > command to install them.')
    return

def SubList(aList,bList):# in a ,not in b  
    tmp = []  
    for a in aList:  
        if a not in bList:  
            tmp.append(a)  
    return tmp  

def AndList(aList,bList):# in a and in b  
    tmp = []  
    for a in aList:  
        if a in bList:  
            tmp.append(a)  
    return tmp  

def OrList(aList,bList):# in a or in b  
    tmp = OnceForList(aList)  
    bList = OnceForList(bList)  
    for a in bList:  
        if a not in tmp:  
            tmp.append(a)  
    return tmp 


def package_update():
    """Update env's packages.

    Compare the old and new software package list and update the package.
    Remove unwanted packages and download the newly selected package.
    Check if the files in the deleted packages have been changed, and if so, 
    remind the user saved the modified file.

    Args:
        none

    Returns:
        none

    Raises:
        none
    """
    bsp_root = Import('bsp_root')
    env_root = Import('env_root')

    flag = True

    #print bsp_root
    #print env_root

    if not os.path.exists('.config'):
        print ("Can't find file .config.Maybe your working directory isn't in bsp root now.")
        print ("if your working directory isn't in bsp root now,please change your working directory to bsp root.")
        print ("if your working directory is in bsp root now, please use menuconfig command to create .config file first.")
        return

    bsp_packages_path = os.path.join(bsp_root,'packages')
    if not os.path.exists(bsp_packages_path):
        os.mkdir("packages")
        os.chdir(bsp_packages_path)
        fp = open("pkgs.json",'w') 
        fp.write("[]")
        fp.close()
        os.chdir(bsp_root)

    # prepare target packages file
    dbsqlite_pathname = os.path.join(bsp_packages_path,'packages.dbsqlite')
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
            fp = open("pkgs.json",'w') 
            fp.write("[]")
            fp.close()
            os.chdir(bsp_root)
            print ("Create a new file pkgs.json done.")

    # Reading data back from pkgs.json
    with open(pkgs_fn, 'r') as f:
        oldpkgs = json.load(f)

    #print "newpkgs:",newpkgs
    #print "oldpkgs:",oldpkgs

    # 1.in old ,not in new  
    casedelete = SubList(oldpkgs,newpkgs)
    for pkg in casedelete:
        dirpath = pkg['path']
        ver = pkg['ver']
        #print 'ver is :',ver[1:]
        if dirpath[0] == '/' or dirpath[0] == '\\': dirpath = dirpath[1:]
        #dirpath = dirpath.replace('/', '\\')
        dirpath = os.path.basename(dirpath) 
        #print "basename:",os.path.basename(dirpath)
        removepath = os.path.join(bsp_packages_path,dirpath)
        removepath_git = os.path.join(removepath,'.git')
        #print "floder to delete",removepath
        #print "removepath_git to delete",removepath_git

        # Delete. Git directory.

        if os.path.isdir(removepath) and os.path.isdir(removepath_git):           
            #uppername = str.upper(str(os.path.basename(removepath)))
            #dirname = os.path.dirname(removepath)
            #gitdir = os.path.join(dirname,uppername)
            gitdir = removepath

            print ("\nOperation : Delete a git package or change the version of a package.")
            print ("If you want to change the version of a package,you should aslo delete the old package before update.\nOtherwise,you may fail to update.\n")
            print ("Folder to delete: %s"%(gitdir))
            print ("The folder is managed by git. Do you want to delete this folder?\n")

            rc = raw_input('Press the Y Key to delete the folder or just press Enter to keep the file:')
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
                        cmd = 'rd /s /q ' + gitdir
                        os.system(cmd)
                    print ("Delete not entirely,try again.")
                else:
                    print ("Folder has been removed.")
        else:
            #print 'removepath' + removepath
            print("Start to remove %s, please wait...\n"%removepath)
            pkgsdb.deletepackdir(removepath,dbsqlite_pathname)

    # 2.in old and in new  
    caseinoperation = AndList(newpkgs,oldpkgs)

    # 3.in new not in old 
    # If the package download fails, record it, and then download again when the update command is executed.

    casedownload = SubList(newpkgs,oldpkgs)
    #print 'in new not in old:',casedownload
    list = []

    for pkg in casedownload:
        if install_pkg(env_root, bsp_root, pkg):                
            print("==============================>  %s %s is downloaded successfully. \n"%(pkg['name'], pkg['ver'] ))
        else: 
            list.append(pkg)                    # If the PKG download fails, record it in the list. 
            print pkg,'download failed.'
            flag = False

    newpkgs = SubList(newpkgs,list)     # Get the currently updated configuration.

    # Give hints based on the success of the download.

    if len(list):
        print("Package download failed list: %s \n"%list)
        print("You need to reuse the 'pkgs -update' command to download again.\n")

    # Writes the updated configuration to pkgs.json file.
    # Packages that are not downloaded correctly will be redownloaded at the next update.

    pkgs_file = file(pkgs_fn, 'w')
    pkgs_file.write(json.dumps(newpkgs, indent=1))
    pkgs_file.close()

    # update SConscript file
    if not os.path.isfile(os.path.join(bsp_packages_path, 'SConscript')):
        bridge_script = file(os.path.join(bsp_packages_path, 'SConscript'), 'w')
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
        if dirpath[0] == '/' or dirpath[0] == '\\': dirpath = dirpath[1:]

        dirpath = os.path.basename(dirpath) 
        removepath = os.path.join(bsp_packages_path,dirpath)
        #print "if floder exist",removepath
        removepath_ver = removepath + '-' + ver[1:]
        #print "if floder exist",removepath

        if os.path.exists(removepath):
            continue
        elif os.path.exists(removepath_ver):
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
                print("==============================>  %s %s is redownloaded successfully. \n"%(pkg['name'], pkg['ver'] ))
            else:
                error_packages_redownload_error_list.append(pkg)
                print pkg,'download failed.'
                flag = False

        if len(error_packages_redownload_error_list):
            print("%s"%error_packages_redownload_error_list)
            print ("Packages:%s,%s redownloed error,you need to use 'pkgs --update' command again to redownload them."%pkg['name'], pkg['ver'])
            write_back_pkgs_json = SubList(read_back_pkgs_json,error_packages_redownload_error_list)
            read_back_pkgs_json = write_back_pkgs_json         
            #print("write_back_pkgs_json:%s"%write_back_pkgs_json)
            pkgs_file = file(pkgs_fn, 'w')
            pkgs_file.write(json.dumps(write_back_pkgs_json, indent=1))
            pkgs_file.close()
    else:
        print("\nAll the selected packages have been downloaded successfully.\n")

    # If the selected package is the latest version, 
    # check to see if it is the latest version after the update command, 
    # if not, then update the latest version from the remote repository.
    # If the download has a conflict, you are currently using the prompt message provided by git.

    payload = {
        "userName": "RT-Thread",
        "packages": [
            {
            "name": "NULL",
            }
        ]
    }

    env_kconfig_path = os.path.join(env_root, 'tools\scripts\cmds')
    env_config_file = os.path.join(env_kconfig_path,'.config')

    beforepath = os.getcwd()
    for pkg in read_back_pkgs_json:
        package = Package()
        pkg_path = pkg['path']
        if pkg_path[0] == '/' or pkg_path[0] == '\\': pkg_path = pkg_path[1:]
        pkg_path = os.path.join(env_root, 'packages', pkg_path, 'package.json')
        package.parse(pkg_path)
        pkgs_name_in_json =  package.get_name()
        if pkg['ver'] == "latest_version" or pkg['ver'] == "latest" :
            repo_path = os.path.join(bsp_packages_path,pkgs_name_in_json)
            ver_sha = package.get_versha(pkg['ver'])
            os.chdir(repo_path)

            if os.path.isfile(env_config_file) and find_macro_in_condfig(env_config_file,'SYS_PKGS_DOWNLOAD_ACCELERATE'):
                payload_pkgs_name_in_json = pkgs_name_in_json.encode("utf-8")
                payload["packages"][0]['name'] = payload_pkgs_name_in_json

                r = requests.post("http://packages.rt-thread.org/packages/queries", data=json.dumps(payload))
                if r.status_code == requests.codes.ok:
                    #print("Software package get Successful")
                    package_info = json.loads(r.text)

                    if len(package_info['packages']) == 0:
                        #print("No packages were found in the mirror server.")
                    else:
                         for item in package_info['packages'][0]['packages_info']['site']:
                            if item['version'] == "latest_version" or item['version'] == "latest":
                                cmd = 'git remote set-url origin ' + item['URL']
                                os.system(cmd)
                                #print(cmd)

            cmd = 'git pull'  # Only one trace relationship can be used directly with git pull.
            os.system(cmd)

            cmd = 'git remote set-url origin ' + package.get_url(pkg['ver'])
            os.system(cmd)
            os.chdir(beforepath)
            print("==============================>  %s update done \n"%(pkgs_name_in_json))

    if flag:
        print ("Operation completed successfully.")
    else:
        print ("Operation failed.")

def package_wizard():
    """Packages creation wizard.

    The user enters the package name, version number, category, and automatically generates the package index file.

    Args:
        package name
        version number
        category

    Returns:
        none

    Raises:
        none
    """

    print ('Welcome to package wizard,please enter the package information.')
    print ('The messages in [] is default setting.You can just press enter to use default Settings.')
    print ('Please enter the name of package:')
    name = raw_input()
    if name == '':
        print ('please provide the package name.\n')
        return

    default_description =  'a ' + name + ' package for rt-thread'
    #description = user_input('menuconfig option name,default:\n',default_description)
    description = default_description
    ver = user_input('version of package,default:\n' ,'1.0.0')
    ver_standard = ver.replace('.','')
    #keyword = user_input('keyword,default:\n', name)
    keyword = name

    packageclass = ('iot', 'language','misc', 'multimedia','security', 'system')
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
    kconfig = s.substitute(name = uppername, description = description, version = ver ,pkgs_class = pkgsclass ,lowercase_name = name ,version_standard = ver_standard)
    f = file(os.path.join(pkg_path, 'Kconfig'), 'wb')
    f.write(kconfig)
    f.close()

    s = Template(Package_json_file)
    package = s.substitute(name = name, description = description, version = ver, keyword = keyword)
    f = file(os.path.join(pkg_path, 'package.json'), 'wb')
    f.write(package)
    f.close()

    s = Template(Sconscript_file)
    sconscript = s.substitute(name = name)
    f = file(os.path.join(pkg_path, 'SConscript'), 'wb')
    f.write(sconscript)
    f.close()

    print ('==============================> Your package index was made successfully.')


def cmd(args):
    env_scripts_root = os.path.join(Import('env_root'), 'tools','scripts')
    packages_root = os.path.join(Import('env_root'), 'packages')
    git_repo = 'https://github.com/RT-Thread/packages.git'
    env_scripts_repo = 'https://github.com/RT-Thread/env.git'

    if args.package_update:
        package_update()
    elif args.package_create:
        package_wizard()
    elif args.package_list:
        package_list()
    elif args.package_upgrade:
        beforepath = os.getcwd()
        pkgs_path = os.path.join(packages_root,'packages')
        #print pkgs_path
        if not os.path.isdir(pkgs_path):
            cmd = 'git clone '+ git_repo + ' '+ pkgs_path
            os.system(cmd)
            print ("upgrade from :%s"%(git_repo))

        for filename in os.listdir(packages_root):
            if os.path.isdir(os.path.join(packages_root,filename)):
                os.chdir(os.path.join(packages_root,filename))
                if os.path.isdir('.git'):
                    cmd = 'git pull origin master'
                    os.system(cmd)
                    os.chdir(beforepath)
                    print("==============================>  Env %s update done \n"%filename)

        beforepath = os.getcwd()
        os.chdir(env_scripts_root)
        cmd = 'git pull '+ env_scripts_repo
        os.system(cmd)
        os.chdir(beforepath)
        print("==============================>  Env scripts update done \n")

    elif args.package_print_env:
         print ("Here are some environmental variables.")
         print ("If you meet some problems,please check them. Make sure the configuration is correct.")
         print ("RTT_EXEC_PATH:%s"%(os.getenv("RTT_EXEC_PATH")))
         print ("RTT_CC:%s"%(os.getenv("RTT_CC")))
         print ("SCONS:%s"%(os.getenv("SCONS")))
         print ("PKGS_ROOT:%s"%(os.getenv("PKGS_ROOT")))

         env_root = os.getenv('ENV_ROOT')
         if env_root == None:
             import platform
             if platform.system() != 'Windows':
                 env_root = os.path.join(os.getenv('HOME'), '.env')

         print ("ENV_ROOT:%s"%(env_root))
         #print "RTT_ROOT:",os.getenv("RTT_ROOT")
         #os.putenv("RTT_EXEC_PATH","rtt_gcc_path")
         #print "after",os.getenv("RTT_EXEC_PATH")
    else:
         os.system('pkgs -h')

def add_parser(sub):
    parser = sub.add_parser('package', help=__doc__, description=__doc__)

    parser.add_argument('--update', 
        help = 'update packages, install or remove the packages as you set in menuconfig',
        action='store_true',
        default=False,
        dest = 'package_update')

    parser.add_argument('--list', 
        help = 'list target packages',
        action='store_true',
        default=False,
        dest = 'package_list')

    parser.add_argument('--wizard', 
        help = 'create a package with wizard',
        action='store_true',
        default=False,
        dest = 'package_create')

    parser.add_argument('--upgrade', 
        help = 'update local packages list from git repo',
        action='store_true',
        default=False,
        dest = 'package_upgrade')

    parser.add_argument('--printenv', 
        help = 'print environmental variables to check',
        action='store_true',
        default=False,
        dest = 'package_print_env')

    #parser.add_argument('--upgrade', dest='reposource', required=False,
    #            help='add source & update packages repo ')

    parser.set_defaults(func=cmd)
