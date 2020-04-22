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

import os
import re
from package import Kconfig_file, Package_json_file
from string import Template
from .cmd_package_utils import user_input


def package_wizard():
    """Packages creation wizard.

    The user enters the package name, version number, category, and automatically generates the package index file.
    """

    # Welcome
    print('\033[4;32;40mWelcome to using package wizard, please follow below steps.\033[0m\n')

    # Simple introduction about the wizard
    print('note :')
    print('      \033[5;35;40m[   ]\033[0m means default setting or optional information.')
    print('      \033[5;35;40mEnter\033[0m means using default option or ending and proceeding to the next step.')

    # first step
    print('\033[5;33;40m\n1.Please input a new package name :\033[0m')

    name = user_input()
    regular_obj = re.compile('\W')
    while name == '' or name.isspace() == True or regular_obj.search(name.strip()):
        if name == '' or name.isspace():
            print('\033[1;31;40mError: you must input a package name. Try again.\033[0m')
            name = user_input()
        else:
            print('\033[1;31;40mError: package name is made of alphabet, number and underline. Try again.\033[0m')
            name = user_input()

    default_description = 'Please add description of ' + name + ' in English.'
    description = default_description
    description_zh = "请添加软件包 " + name + " 的中文描述。"

    # second step
    print("\033[5;33;40m\n2.Please input this package version, default : '1.0.0' \033[0m")
    ver = user_input()
    if ver == '':
        print("using default version 1.0.0")
        ver = '1.0.0'

    ver_standard = ver.replace('.', '')
    keyword = name

    # third step
    package_class_list = ('iot', 'language', 'misc', 'multimedia',
                          'peripherals', 'security', 'system', 'tools', 'peripherals/sensors')
    print('\033[5;33;40m\n3.Please choose a package category from 1 to 9 : \033[0m')
    print("\033[1;32;40m[1:iot]|[2:language]|[3:misc]|[4:multimedia]|"
          "[5:peripherals]|[6:security]|[7:system]|[8:tools]|[9:sensors]\033[0m")

    class_number = user_input()
    while class_number == '' or class_number.isdigit() is False or int(class_number) < 1 or int(class_number) > 9:
        if class_number == '':
            print('\033[1;31;40mError: You must choose a package category. Try again.\033[0m')
        else:
            print('\033[1;31;40mError: You must input an integer number from 1 to 9. Try again.\033[0m')
        class_number = user_input()

    package_class = package_class_list[int(class_number) - 1]

    # fourth step
    print("\033[5;33;40m\n4.Please input author's github ID of this package :\033[0m")

    author_name = user_input()
    while author_name == '':
        print("\033[1;31;40mError: you must input author's github ID of this package. Try again.\033[0m")
        author_name = user_input()

    # fifth step
    author_email = user_input('\033[5;33;40m\n5.Please input author email of this package :\n\033[0m')
    while author_email == '':
        print('\033[1;31;40mError: you must input author email of this package. Try again.\033[0m')
        author_email = user_input()

    # sixth step
    print('\033[5;33;40m\n6.Please choose a license of this package from 1 to 4, or input other license name :\033[0m')
    print("\033[1;32;40m[1:Apache-2.0]|[2:MIT]|[3:LGPL-2.1]|[4:GPL-2.0]\033[0m")
    license_index = ('Apache-2.0', 'MIT', 'LGPL-2.1', 'GPL-2.0')
    license_class = user_input()
    while license_class == '':
        print('\033[1;31;40mError: you must choose or input a license of this package. Try again.\033[0m')
        license_class = user_input()

    if license_class.isdigit() and 1 <= int(license_class) <= 4:
        license_choice = license_index[int(license_class) - 1]
    else:
        license_choice = license_class

    # seventh step
    print('\033[5;33;40m\n7.Please input the repository of this package :\033[0m')
    print(
        "\033[1;32;40mFor example, hello package's repository url "
        "is 'https://github.com/RT-Thread-packages/hello'.\033[0m")

    repository = user_input()
    while repository == '':
        print('\033[1;31;40mError: you must input a repository of this package. Try again.\033[0m')
        repository = user_input()

    pkg_path = name
    if not os.path.exists(pkg_path):
        os.mkdir(pkg_path)
    else:
        print("\033[1;31;40mError: the package directory is exits!\033[0m")

    s = Template(Kconfig_file)
    upper_name = str.upper(name)
    kconfig = s.substitute(name=upper_name, description=description, version=ver,
                           pkgs_class=package_class, lowercase_name=name, version_standard=ver_standard)
    f = open(os.path.join(pkg_path, 'Kconfig'), 'w')
    f.write(kconfig)
    f.close()

    s = Template(Package_json_file)
    package = s.substitute(name=name, pkgsclass=package_class, authorname=author_name, authoremail=author_email,
                           description=description, description_zh=description_zh, version=ver, keyword=keyword,
                           license=license_choice, repository=repository, pkgs_using_name=upper_name)
    f = open(os.path.join(pkg_path, 'package.json'), 'w')
    f.write(package)
    f.close()

    print('\nThe package index has been created \033[1;32;40msuccessfully\033[0m.')
    print('Please \033[5;34;40mupdate\033[0m other information of this package '
          'based on Kconfig and package.json in directory ' + name + '.')

