import os
import platform
import kconfig
from package import Package
from vars import Import


def list_packages():
    """Print the packages list in env.

    Read the.config file in the BSP directory,
    and list the version number of the selected package.
    """

    fn = '.config'
    env_root = Import('env_root')
    pkgs_root = Import('pkgs_root')

    if not os.path.isfile(fn):
        if platform.system() == "Windows":
            os.system('chcp 65001  > nul')

        print("\033[1;31;40mCan't find system configuration file : .config.\033[0m")
        print('\033[1;31;40mYou should use < menuconfig > command to config bsp first.\033[0m')

        if platform.system() == "Windows":
            os.system('chcp 437  > nul')

        return

    pkgs = kconfig.parse(fn)

    for pkg in pkgs:
        package = Package()
        pkg_path = pkg['path']
        if pkg_path[0] == '/' or pkg_path[0] == '\\':
            pkg_path = pkg_path[1:]

        pkg_path = os.path.join(pkgs_root, pkg_path, 'package.json')
        package.parse(pkg_path)

        pkgs_name_in_json = package.get_name()
        print("package name : %s, ver : %s " % (pkgs_name_in_json.encode("utf-8"), pkg['ver'].encode("utf-8")))

    if not pkgs:
        print("Packages list is empty.")
        print('You can use < menuconfig > command to select online packages.')
        print('Then use < pkgs --update > command to install them.')
    return
