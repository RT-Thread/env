import os
import sys
import argparse

from cmds    import *
from vars    import Import, Export

__version__ = 'rt-thread packages v1.0.0'

def init_argparse():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers()

    parser.add_argument('-v', '--version', action='version', version=__version__)

    cmd_system.add_parser(subs)
    cmd_menuconfig.add_parser(subs)
    cmd_package.add_parser(subs)

    return parser

if __name__ == '__main__':

    bsp_root = os.getcwd()
    script_root = os.path.split(os.path.realpath(__file__))[0]
    env_root = os.getenv("ENV_ROOT")

    sys.path = sys.path + [os.path.join(script_root)]

    Export('env_root')
    Export('bsp_root')

    parser = init_argparse()
    args = parser.parse_args()
    args.func(args)
