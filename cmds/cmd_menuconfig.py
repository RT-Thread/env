import os
import argparse
from cmd_package import package_update
from vars import Import, Export
'''menuconfig for system configuration'''

# make rtconfig.h from .config

def mk_rtconfig(filename):
    try:
        config = file(filename)
    except:
        print 'open .config failed'
        return

    rtconfig = file('rtconfig.h', 'w')
    rtconfig.write('#ifndef RT_CONFIG_H__\n')
    rtconfig.write('#define RT_CONFIG_H__\n\n')

    empty_line = 1

    for line in config:
        line = line.lstrip(' ').replace('\n', '').replace('\r', '')

        if len(line) == 0: continue

        if line[0] == '#':
            if len(line) == 1:
                if empty_line:
                    continue

                rtconfig.write('\n')
                empty_line = 1
                continue

            comment_line = line[1:]
            if line.startswith('# CONFIG_'): line = ' ' + line[9:]
            else: line = line[1:]

            rtconfig.write('/*%s */\n' % line)
            empty_line = 0
        else:
            empty_line = 0
            setting = line.split('=')
            if len(setting) >= 2:
                if setting[0].startswith('CONFIG_'):
                    setting[0] = setting[0][7:]

                # remove CONFIG_PKG_XX_PATH or CONFIG_PKG_XX_VER
                if type(setting[0]) == type('a') and (setting[0].endswith('_PATH') or setting[0].endswith('_VER')):
                    continue

                if setting[1] == 'y':
                    rtconfig.write('#define %s\n' % setting[0])
                else:
                    rtconfig.write('#define %s %s\n' % (setting[0], setting[1]))

    if os.path.isfile('rtconfig_project.h'):
        rtconfig.write('#include "rtconfig_project.h"\n')

    rtconfig.write('\n')
    rtconfig.write('#endif\n')
    rtconfig.close()

def cmd(args):
    currentdir = os.getcwd() 
    dirname = os.path.split(os.path.split(currentdir)[0])[0]
    get_rtt_name = os.path.basename(dirname)
    #print os.path.split(currentdir)[1]

    if not os.getenv("RTT_ROOT"):
        if get_rtt_name != 'rt-thread':  
            print "menuconfig command should be used in a bsp root path with a Kconfig file,you should check if there is a Kconfig file in your bsp root first."
            print 'And then you can check Kconfig file and modify the default option below to your rtthread root path.\n'

            print 'config $RTT_DIR'
            print 'string' 
            print 'option env="RTT_ROOT"'
            print 'default "../.."\n'
            print 'example:  default "F:/git_repositories/rt-thread"  \n'

            print "using command 'set RTT_ROOT=your_rtthread_root_path' to set RTT_ROOT is ok too.\n"
            print "you can ignore debug messages below."
            #if not args.menuconfig_easy:                
            #    return

    fn = '.config'

    if os.path.isfile(fn):
        mtime = os.path.getmtime(fn)
    else:
        mtime = -1

    if args.menuconfig_fn:
        print 'use', args.menuconfig_fn
        import shutil
        shutil.copy(args.menuconfig_fn, fn)
    elif args.menuconfig_silent:
        os.system('kconfig-mconf Kconfig -n')
    else:
        os.system('kconfig-mconf Kconfig')

    if os.path.isfile(fn):
        mtime2 = os.path.getmtime(fn)
    else:
        mtime2 = -1

    if mtime != mtime2:
        mk_rtconfig(fn)

    if not args.menuconfig_skipupdate:
        package_update()

def add_parser(sub):
    parser = sub.add_parser('menuconfig', help=__doc__, description=__doc__)

    parser.add_argument('--config', 
        help = 'Using the user specified configuration file.',
        dest = 'menuconfig_fn')

    parser.add_argument('--silent', 
        help = 'Silent mode,don\'t display menuconfig window.',
        action='store_true',
        default=False,
        dest = 'menuconfig_silent')

    parser.add_argument('-s','--skipupdate', 
    help = 'if you add "-s",you will skip command "pkgs --update" and do not update the packages.',
    action='store_true',
    default=False,
    dest = 'menuconfig_skipupdate')

    parser.add_argument('--easy', 
    help = 'easy mode,place kconfig file everywhere,just modify the option env="RTT_ROOT" default "../.."',
    action='store_true',
    default=False,
    dest = 'menuconfig_easy')

    parser.set_defaults(func=cmd)
