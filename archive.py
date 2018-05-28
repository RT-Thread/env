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
#

import tarfile
import zipfile
import os
import pkgsdb


def unpack(archive_fn, path):
    if ".tar.bz2" in archive_fn:
        arch = tarfile.open(archive_fn, "r:bz2")
        for tarinfo in arch:
            arch.extract(tarinfo, path)            
            a = tarinfo.name           
            if not os.path.isdir(os.path.join(path,a)):
                right_path = a.replace('/','\\')
                a = os.path.join(os.path.split(right_path)[0],os.path.split(right_path)[1]) 
                pkgsdb.savetodb(a,archive_fn)
        arch.close()

    if ".tar.gz" in archive_fn:
        arch = tarfile.open(archive_fn, "r:gz")
        for tarinfo in arch:
            arch.extract(tarinfo, path)
            a = tarinfo.name
            if not os.path.isdir(os.path.join(path,a)):
                right_path = a.replace('/','\\')
                a = os.path.join(os.path.split(right_path)[0],os.path.split(right_path)[1]) 
                pkgsdb.savetodb(a,archive_fn)
        arch.close()

    if ".zip" in archive_fn:
        arch = zipfile.ZipFile(archive_fn, "r")
        for item in arch.namelist():
            arch.extract(item, path)
            if not os.path.isdir(os.path.join(path,item)):
                right_path = item.replace('/','\\')          
                #print "here to extract files:",item
                item = os.path.join(os.path.split(right_path)[0],os.path.split(right_path)[1]) 
                pkgsdb.savetodb(item,archive_fn)
        arch.close()

def packtest(path):
    ret = True
    if ".zip" in path:
        try:
            if zipfile.is_zipfile(path):
            # test zip again to make sure it's a right zip file.
                arch = zipfile.ZipFile(path, "r")
                if arch.testzip():
                    ret = False
                arch.close()                    
        except Exception, e:
            print('e.message:%s\t'%e.message)
            arch.close()
            ret = False
                
    if ".tar.bz2" in path:
        try:
            if not tarfile.is_tarfile(path):
                ret = False                    
        except Exception, e:
            ret = False

    if ".tar.gz" in path:
        try:
            if not tarfile.is_tarfile(path):
                ret = False                    
        except Exception, e:
            ret = False
                    
    return ret
