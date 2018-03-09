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

from package import Package
from vars import Import, Export
from string import Template

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
            bool "latest_version"
    endchoice
    
    if PKG_USING_${name}_V${version_standard}
        config PKG_${name}_VER
        string
        default "v${version}"
    endif
   
    if PKG_USING_${name}_LATEST_VERSION
       config PKG_${name}_VER
       string
       default "latest_version"    
    endif

endif

'''

Package_json_file = '''
{
    "name": "${name}",
    "description": "${description}",
    "keywords": [
        "${keyword}"
    ],
    "readme": "${description}",
    "site" : [
    {"version" : "v${version}", "URL" : "https://${name}-${version}.zip", "filename" : "${name}-${version}.zip","VER_SHA" : "fill in the git version SHA value"},
    {"version" : "latest_version", "URL" : "https://xxxxx.git", "filename" : "Null for git package","VER_SHA" : "fill in latest version branch name,such as mater"}
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

    package = Package()
    pkg_path = pkg['path']
    if pkg_path[0] == '/' or pkg_path[0] == '\\': pkg_path = pkg_path[1:]

    #pkg_path = pkg_path.replace('/', '\\')
    pkg_path = os.path.join(env_root, 'packages', pkg_path, 'package.json')

    package.parse(pkg_path)

    package_url = package.get_url(pkg['ver'])
    package_name = pkg['name']
    pkgs_name_in_json =  package.get_name()

    #print "get name here:",pkgs_name_in_json
    #print "url:",package_url
    #print "name:",package_name
   
    beforepath = os.getcwd()

    if package_url[-4:] == '.git':
        ver_sha = package.get_versha(pkg['ver'])
        repo_path = os.path.join(bsp_pkgs_path,pkgs_name_in_json)
        cmd = 'git clone '+ package_url + ' '+ repo_path
        os.system(cmd)
        os.chdir(repo_path)
        cmd = 'git checkout '+ ver_sha
        os.system(cmd)
        cmd = 'git submodule init '
        os.system(cmd)
        cmd = 'git submodule update '
        if not os.system(cmd):
            print "Submodule update success"
        os.chdir(beforepath)
    else:
        # download package
        if not package.download(pkg['ver'], local_pkgs_path):
            ret = False
            return ret

        pkg_dir = package.get_filename(pkg['ver'])
        pkg_dir = os.path.splitext(pkg_dir)[0]

        pkg_fullpath = os.path.join(local_pkgs_path, package.get_filename(pkg['ver']))

        # unpack package
        if not os.path.exists(pkg_dir):
            package.unpack(pkg_fullpath, bsp_pkgs_path)
            ret = True

    return ret

""" 
读取bsp目录下的.config文件，列出已选用的软件包的名称的版本号
""" 
def package_list():
    fn = '.config'
    env_root = Import('env_root')
    bsp_root = Import('bsp_root')
    target_pkgs_path = os.path.join(bsp_root, 'packages')
    pkgs_fn = os.path.join(target_pkgs_path, 'pkgs.json')

    if not os.path.isfile(fn):
        print 'no system configuration file : .config.'
        print 'you should use < menuconfig > command to config bsp first.'
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
        print "Packages list is empty."
        print 'You can use < menuconfig > command to select online packages.'
        print 'Then use < pkgs --update > command to install them.'
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


""" 
对比新旧软件包列表，对软件包进行更新。删除不需要的软件包，下载新选中的软件包。
检查删除的软件包里的文件是否有改动，如果有那么提示用户是否保存修改的文件。
""" 
def package_update():
    bsp_root = Import('bsp_root')
    env_root = Import('env_root')

    flag = True

    #print bsp_root
    #print env_root

    if not os.path.exists('.config'):
        print "Can't find file .config.Maybe your working directory isn't in bsp root now."
        print "if your working directory isn't in bsp root now,please change your working directory to bsp root."
        print "if your working directory is in bsp root now, please use menuconfig command to create .config file first."
        return

    packages_bsp = os.path.join(bsp_root,'packages')
    if not os.path.exists(packages_bsp):
        os.mkdir("packages")
        os.chdir(os.path.join(bsp_root,'packages'))
        fp = open("pkgs.json",'w') 
        fp.write("[]")
        fp.close()
        os.chdir(bsp_root)

    # prepare target packages file
    target_pkgs_path = os.path.join(bsp_root, 'packages')
    dbsqlite_pathname = os.path.join(target_pkgs_path,'packages.dbsqlite')
    Export('dbsqlite_pathname')

    #Avoid creating tables more than one time
    if not os.path.isfile(dbsqlite_pathname):                              
        conn = pkgsdb.get_conn(dbsqlite_pathname)
        sql = '''CREATE TABLE packagefile
                    (pathname   TEXT  ,package  TEXT  ,md5  TEXT );'''
        pkgsdb.create_table(conn, sql)

    fn = '.config'
    pkgs = kconfig.parse(fn)
    newpkgs = pkgs

    if not os.path.exists(target_pkgs_path):
        os.mkdir(target_pkgs_path)

    pkgs_fn = os.path.join(target_pkgs_path, 'pkgs.json')

    if not os.path.exists(pkgs_fn):
        print "Maybe you delete the file pkgs.json by mistake."
        print "Do you want to create a new pkgs.json ?"
        rc = raw_input('Press the Y Key to create a new pkgs.json.')
        if rc == 'y' or rc == 'Y':
            os.chdir(os.path.join(bsp_root,'packages'))
            fp = open("pkgs.json",'w') 
            fp.write("[]")
            fp.close()
            os.chdir(bsp_root)
            print "Create a new file pkgs.json down."

    # Reading data back
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
        removepath = os.path.join(target_pkgs_path,dirpath)
        #print "floder to delere",removepath

        #处理.git目录的删除
        if os.path.isdir(removepath):           
            #uppername = str.upper(str(os.path.basename(removepath)))
            #dirname = os.path.dirname(removepath)
            #gitdir = os.path.join(dirname,uppername)
            gitdir = removepath

            print "\nOperation : Delete a git package or change the version of a package."
            print "If you want to change the version of a package,you should aslo delete the old package before update.\nOtherwise,you may fail to update.\n"
            print "Folder to delete: ",gitdir
            print "The folder is managed by git,are you sure you want to delete this folder?\n"

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
                    print "Delete not entirely,try again."
                else:
                    print "Folder has been removed."
        else:
            #生成普通解压路径并删除
            removepath = removepath + '-' + ver[1:]
            #print removepath
            pkgsdb.deletepackdir(removepath,dbsqlite_pathname)

    # 2. in old and in new  
    caseinoperation = AndList(newpkgs,oldpkgs)

    # 3.in new not in old   下载失败应该重新处理，不需要再次配置。
    
    casedownload = SubList(newpkgs,oldpkgs)
    #print 'in new not in old:',casedownload
    list = []

    for pkg in casedownload:
        if not install_pkg(env_root, bsp_root, pkg):
            #如果pkg下载失败则记录到list中            
            list.append(pkg)
            print pkg,'download failed.'
            flag = False
        print("==============================>  %s %s is downloaded  \n"%(pkg['name'], pkg['ver'] ))

    newpkgs = SubList(newpkgs,list)     #获得目前更新好的配置

    #print "update old config to:",newpkgs

    # update pkgs.json file  
    pkgs_file = file(pkgs_fn, 'w')
    pkgs_file.write(json.dumps(newpkgs, indent=1))
    pkgs_file.close()

    # update SConscript file
    if not os.path.isfile(os.path.join(target_pkgs_path, 'SConscript')):
        bridge_script = file(os.path.join(target_pkgs_path, 'SConscript'), 'w')
        bridge_script.write(Bridge_SConscript)
        bridge_script.close()

    #如果选择的软件包为最新版本那么在update命令之后检查目前是否是最新版本，如果不是，那么从远程仓库更新最新版本
    #如果下载有冲突，目前使用git提供的提示信息
    fn = '.config'
    beforepath = os.getcwd()
    pkgs = kconfig.parse(fn)
    for pkg in pkgs:
        package = Package()
        pkg_path = pkg['path']
        if pkg_path[0] == '/' or pkg_path[0] == '\\': pkg_path = pkg_path[1:]
        pkg_path = os.path.join(env_root, 'packages', pkg_path, 'package.json')
        package.parse(pkg_path)
        pkgs_name_in_json =  package.get_name()
        if pkg['ver'] == "latest_version" or pkg['ver'] == "latest" :
            repo_path = os.path.join(target_pkgs_path,pkgs_name_in_json)
            ver_sha = package.get_versha(pkg['ver'])
            #print repo_path, ver_sha 
            #只有一种追踪关系可以直接使用git pull

            if os.path.exists(repo_path):
                os.chdir(repo_path)
                cmd = 'git pull'
                os.system(cmd)
                os.chdir(beforepath)
                print("==============================>  %s update done \n"%(pkgs_name_in_json))
            else:
                print("==============================>  %s is not downloaded correctly, please download it again. \n"%(pkgs_name_in_json))

    if flag:
        print "operate successfully."
    else:
        print "operate failed."

def package_wizard():
    print 'Welcome come to package wizard,please enter the package information.'
    print 'The messages in [] is default setting.You can just press enter to use default Settings.'
    print 'Please enter the name of package:'
    name = raw_input()
    if name == '':
        print 'please provide the package name.\n'
        return

    default_description =  'a ' + name + ' package for rt-thread'
    #description = user_input('menuconfig option name,default:\n',default_description)
    description = default_description
    ver = user_input('version of package,default:\n' ,'1.0.0')
    ver_standard = ver.replace('.','')
    #keyword = user_input('keyword,default:\n', name)
    keyword = name

    packageclass = ('iot', 'language','misc', 'multimedia','security', 'system')
    print 'Please choose a class for your packages.'
    print 'Enter 1 for iot and 2 for language, following the table below as a guideline.'
    print "[1:iot]|[2:language]|[3:misc]|[4:multimedia]|[5:security]|[6:system]"

    classnu = raw_input()
    if classnu == '':
        print 'You must choose a class for your packages.Try again.\n'
        return

    if classnu >= '1' and classnu <= '6':
        pkgsclass = packageclass[int(classnu) - 1]
        #print pkgsclass
    else:
        print 'You must type in number 1 to 6.'
        return
        
    pkg_path = name
    if not os.path.exists(pkg_path):
        os.mkdir(pkg_path)
    else:
        print "Warning: the package directory exits!"

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

    print 'packages making success.'


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
            print "upgrade from :",git_repo

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
         print "Here are some environmental variables."
         print "If you meet some problems,please check them. Make sure the configuration is correct."
         print "RTT_EXEC_PATH:",os.getenv("RTT_EXEC_PATH")
         print "RTT_CC:",os.getenv("RTT_CC")
         print "SCONS:",os.getenv("SCONS")
         print "PKGS_ROOT:",os.getenv("PKGS_ROOT")

         env_root = os.getenv('ENV_ROOT')
         if env_root == None:
             import platform
             if platform.system() != 'Windows':
                 env_root = os.path.join(os.getenv('HOME'), '.env')

         print "ENV_ROOT:",env_root
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
