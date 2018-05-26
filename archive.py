# -*- coding:utf-8 -*-
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
