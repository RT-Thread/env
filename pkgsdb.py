# -*- coding:utf-8 -*-
import sqlite3
import os
import hashlib
import tarfile
import bz2
import zipfile

from vars import Import, Export
SHOW_SQL = False

def GetFileMd5(filename):
    if not os.path.isfile(filename):
        return
    myhash = hashlib.md5()
    f = file(filename,'rb')
    while True:
        b = f.read(8096)
        if not b :
            break
        myhash.update(b)
    f.close()
    return myhash.hexdigest()

def get_conn(path):
    conn = sqlite3.connect(path)
    if os.path.exists(path) and os.path.isfile(path):
        #print('on disk:[{}]'.format(path))
        return conn
    else:
        conn = None
        print('on memory:[:memory:]')
        return sqlite3.connect(':memory:')

def close_all(conn, cu):
    if conn is not None:
        conn.close()

def get_cursor(conn):
    if conn is not None:
        return conn.cursor()
    else:
        return get_conn('').cursor()

def create_table(conn, sql):
    if sql is not None and sql != '':
        cu = get_cursor(conn)
        if SHOW_SQL:
            print('执行sql:[{}]'.format(sql))
        cu.execute(sql)
        conn.commit()
        #print('create data table successful!')
        close_all(conn, cu)
    else:
        print('the [{}] is empty or equal None!'.format(sql))

def save(conn, sql, data):
    '''插入数据'''
    if sql is not None and sql != '':
        if data is not None:
            cu = get_cursor(conn)
            for d in data:
                if SHOW_SQL:
                    print('execute sql:[{}],arguments:[{}]'.format(sql, d))
                cu.execute(sql, d)
                conn.commit()
            close_all(conn, cu)
    else:
        print('the [{}] is empty or equal None!'.format(sql))

def isdataexist(pathname):
    ret = True
    dbpathname = Import('dbsqlite_pathname')

    conn = get_conn(dbpathname)
    c = get_cursor(conn) 
    sql = 'SELECT md5 from packagefile where pathname = "' + pathname + '"'
    cursor = c.execute(sql)
    for row in cursor:
        dbmd5 = row[0]
    if dbmd5:
        ret = False
    conn.close()
    return ret

#将数据添加到数据库，如果数据库中已经存在则不重复添加
def savetodb(pathname,pkgspathname):
    dbpathname = Import('dbsqlite_pathname')
    bsp_root = Import('bsp_root')
    bsppkgs = bsp_root + '\\packages\\'
    #print bsppkgs

    conn = get_conn(dbpathname)
    c = get_cursor(conn)
    save_sql = '''insert into packagefile values (?, ?, ?)'''
    package = os.path.basename(pkgspathname)
    #print "pathname",pathname
    md5pathname = bsppkgs + pathname
    md5 = GetFileMd5(md5pathname)
    #print "md5",md5
    data = [(pathname,package ,md5)]
    save(conn, save_sql, data)

def dbdump(dbpathname):
    conn = get_conn(dbpathname)
    c = get_cursor(conn) 
    cursor = c.execute("SELECT pathname, package, md5 from packagefile")
    for row in cursor:
       print "pathname = ", row[0]
       print "package = ", row[1]
       print "md5 = ", row[2], "\n"
    conn.close()

#delete the unchanged file
def remove_unchangedfile(pathname,dbpathname,dbsqlname):
    flag = True

    conn = get_conn(dbpathname)
    c = get_cursor(conn)

    filemd5 = GetFileMd5(pathname)
    #print "filemd5:",filemd5
    dbmd5 = 0

    sql = 'SELECT md5 from packagefile where pathname = "' + dbsqlname + '"'
    #print sql
    cursor = c.execute(sql)
    for row in cursor:
        dbmd5 = row[0]       #fetch md5 from databas      
    #print "dbmd5:",dbmd5

    if dbmd5 == filemd5:
        # delete file info from database
        sql = "DELETE from packagefile where pathname = '" + dbsqlname + "'"
        cursor = c.execute(sql)
        conn.commit()
        os.remove(pathname)       
    else:
        print pathname,"has been changed."
        print 'Are you sure you want to permanently delete the file:',os.path.basename(pathname),'?'
        print 'If you choose to keep the changed file,you should copy the file to another folder. becaues it may be covered by the next update.'
        rc = raw_input('Press the Y Key to delete the file or just press Enter to keep the file.')
        if rc == 'y' or rc == 'Y':
            sql = "DELETE from packagefile where pathname = '" + dbsqlname + "'"
            cursor = c.execute(sql)
            conn.commit()
            os.remove(pathname)
            print pathname,"has been removed.\n"
        else:
           flag = False
    conn.close()
    return flag

#删除一个包，如果有文件被改动，则提示(y/n)是否要删除，输入y则删除文件，输入其他字符则保留文件。
#如果没有文件被改动，直接删除文件夹,包文件夹被完全删除返回true，有被修改的文件没有被删除返回false
def deletepackdir(dirpath,dbpathname):
    bsp_root = Import('bsp_root')
    #print "bsproot:",bsp_root
    #print "dirpath",dirpath
    #print "os.split:", os.path.split(dirpath)[1]
    path = os.path.split(dirpath)[1]
    flag = True

    flag = getdirdisplay(dirpath,dbpathname)

    if flag == True:
        if os.path.exists(dirpath):
            for root, dirs, files in os.walk(dirpath, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(dirpath)
        #print "the dir should be delete"
    return flag

#遍历filepath下所有文件，包括子目录

def displaydir(filepath,basepath,length,dbpathname):
    flag = True
    if os.path.isdir(filepath):
        files = os.listdir(filepath)
        for fi in files:
            fi_d = os.path.join(filepath,fi)
            if os.path.isdir(fi_d):
                displaydir(fi_d,basepath,length,dbpathname)
            else:
                pathname = os.path.join(filepath,fi_d)
                dbsqlname =  basepath + os.path.join(filepath,fi_d)[length:]
                #print dbsqlname
                if not remove_unchangedfile(pathname,dbpathname,dbsqlname):
                   flag = False
    return flag

def getdirdisplay(filepath,dbpathname):
    flag = True
    display = filepath + '\\'
    length = len(display)
    basepath = os.path.basename(filepath) + '\\'
    #print "basepath:",basepath
    flag = displaydir(filepath,basepath,length,dbpathname)
    return flag

def main():  
    DB_FILE_PATH = 'F:\env\sample\packages\packages.dbsqlite'
    TABLE_NAME = 'packagesfile'
    path = "F:\env\sample\packages\hello-1.0.0"

    #conn = get_conn(DB_FILE_PATH)
    #c = get_cursor(conn) 
    #sql = '''DELETE from packagefile where package = "hello-1.0.0.zip"'''
    ##sql = '''DELETE from packagefile where package = ''' 
    ##sql += repr('hello-1.0.0.zip')

    ##sql = "DELETE from packagefile where pathname = '" + pathname + "'"
    ##sql += repr(pathname)
    #print sql
    #c.execute(sql)
    #conn.commit()
    #conn.close()

    #deletepackdir(path,DB_FILE_PATH)
    archive_fn = "F:\\env\\tools\\summer-1.0.0.tar.bz2"
    path = "F:\env\sample\packages\paho-mqtt-1.0.0"

    #getdirdisplay(path,DB_FILE_PATH)

    #dbdump(DB_FILE_PATH)

    repo_path = 'F:\\22'
    repo_url = 'https://github.com/RT-Thread/jerryscript.git'
    #repo_url = 'https://github.com/SummerGGift/Python-Program.git' 
    #repo_url =  'https://github.com/jerryscript-project/jerryscript.git'
    #repo = Gittle.clone(repo_url, repo_path)
    
    print os.getcwd()

    bsp_pkgs_path = "F:\\git_repositories\\env\\sample\\packages"

    #os.chdir(repo_path)
    #cmd = 'git clone https://github.com/RT-Thread/jerryscript.git ' + repo_path
    #os.system(cmd)
    #cmd = 'git submodule init '
    #os.system(cmd)
    #cmd = 'git submodule update '
    #os.system(cmd)

    fp = open("pkgs.json",'w') 
    fp.close()



if __name__ == '__main__':
    main()