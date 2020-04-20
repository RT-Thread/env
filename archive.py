# -*- coding:utf-8 -*-
#
# File      : archive.py
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
# 2020-4-10      SummerGift      Code clear up
#

import tarfile
import zipfile
import os
import pkgsdb
import platform
import shutil
import logging


def is_windows():
    if platform.system() == "Windows":
        return True
    else:
        return False


def remove_folder(folder_path):
    if os.path.isdir(folder_path):
        if is_windows():
            cmd = 'rd /s /q ' + folder_path
            os.system(cmd)
        else:
            shutil.rmtree(folder_path)


def unpack(archive_filename, path, package_info, package_name):
    package_version = package_info['ver']

    package_temp_path = os.path.join(path, "package_temp")
    os.makedirs(package_temp_path)

    logging.info("BSP packages path {0}".format(path))
    logging.info("BSP package temp path: {0}".format(package_temp_path))
    logging.info("archive filename : {0}".format(archive_filename))

    if ".tar.bz2" in archive_filename:
        arch = tarfile.open(archive_filename, "r:bz2")
        for tarinfo in arch:
            arch.extract(tarinfo, path)
            a = tarinfo.name
            if not os.path.isdir(os.path.join(path, a)):
                if is_windows():
                    right_path = a.replace('/', '\\')
                else:
                    right_path = a
                a = os.path.join(os.path.split(right_path)[0], os.path.split(right_path)[1])

                pkgsdb.save_to_database(a, archive_filename)
        arch.close()

    if ".tar.gz" in archive_filename:
        arch = tarfile.open(archive_filename, "r:gz")
        for tarinfo in arch:
            arch.extract(tarinfo, path)
            a = tarinfo.name
            if not os.path.isdir(os.path.join(path, a)):
                if is_windows():
                    right_path = a.replace('/', '\\')
                else:
                    right_path = a
                a = os.path.join(os.path.split(right_path)[0], os.path.split(right_path)[1])
                pkgsdb.save_to_database(a, archive_filename)
        arch.close()

    try:
        if ".zip" in archive_filename:
            flag = True
            dir_name = ""
            package_name_with_version = ""

            arch = zipfile.ZipFile(archive_filename, "r")
            for item in arch.namelist():
                arch.extract(item, package_temp_path)
                if not os.path.isdir(os.path.join(package_temp_path, item)):
                    if is_windows():
                        right_path = item.replace('/', '\\')
                    else:
                        right_path = item

                    # Gets the folder name and changed folder name only once
                    if flag:
                        dir_name = os.path.split(right_path)[0]
                        package_name_with_version = package_name + '-' + package_version
                        flag = False

                    right_name_to_db = right_path.replace(dir_name, package_name_with_version, 1)
                    right_path = os.path.join("package_temp", right_path)
                    pkgsdb.save_to_database(right_name_to_db, archive_filename, right_path)
            arch.close()
    except Exception as e:
        # remove temp folder and archive file
        logging.warning('unpack error message : {0}'.format(e))
        logging.warning('unpack {0} failed'.format(os.path.basename(archive_filename)))
        remove_folder(package_temp_path)
        os.remove(archive_filename)
        return False

    # rename package folder name
    package_name_with_version = package_name + '-' + package_version
    rename_path = os.path.join(package_temp_path, package_name_with_version)
    os.rename(os.path.join(package_temp_path, dir_name), rename_path)

    # copy package to bsp packages path.
    shutil.move(rename_path, os.path.join(path, package_name_with_version))

    # remove temp folder
    remove_folder(package_temp_path)
    return True


def package_integrity_test(path):
    ret = True

    if path.find(".zip") != -1:
        try:
            if zipfile.is_zipfile(path):
                # Test zip again to make sure it's a right zip file.
                arch = zipfile.ZipFile(path, "r")
                if arch.testzip():
                    ret = False
                arch.close()
            else:
                ret = False
                print('package check error. \n')
        except Exception as e:
            print('Package test error message:%s\t' % e)
            print("The archive package is broken. \n")
            arch.close()
            ret = False

    # if ".tar.bz2" in path:.
    if path.find(".tar.bz2") != -1:
        try:
            if not tarfile.is_tarfile(path):
                ret = False
        except Exception as e:
            print('Error message:%s' % e)
            ret = False

    # if ".tar.gz" in path:
    if path.find(".tar.gz") != -1:
        try:
            if not tarfile.is_tarfile(path):
                ret = False
        except Exception as e:
            print('Error message:%s' % e)
            ret = False

    return ret
