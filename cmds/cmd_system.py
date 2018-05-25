import os
from vars import Import

'''RT-Thread environment package system'''

def cmd(args):
    packages_root = os.path.join(Import('env_root'), 'packages')

    if args.system_update:
        dir_list = os.listdir(packages_root)

        kconfig = file(os.path.join(packages_root, 'Kconfig'), 'w')

        for item in dir_list:
            if os.path.isfile(os.path.join(packages_root, item, 'Kconfig')):
                kconfig.write('source "$PKGS_DIR/' + item + '/Kconfig"')
                kconfig.write('\n')

        kconfig.close()
  
def add_parser(sub):
    parser = sub.add_parser('system', help=__doc__, description=__doc__)

    parser.add_argument('--update', 
        help = 'update system menuconfig\'s online package options ',
        action='store_true',
        default=False,
        dest = 'system_update')

    parser.set_defaults(func=cmd)
