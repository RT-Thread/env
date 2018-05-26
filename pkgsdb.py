# -*- coding:utf-8 -*-
import sqlite3
import os
import hashlib

from vars import Import, Export
SHOW_SQL = False


def GetFileMd5(filename):
    if not os.path.isfile(filename):
        return
    myhash = hashlib.md5()
    f = file(filename, 'rb')
    while True:
        b = f.read(8096)
        if not b:
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


def close_all(conn):
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
        close_all(conn)
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
            close_all(conn)
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
def savetodb(pathname, pkgspathname):
    dbpathname = Import('dbsqlite_pathname')
    bsp_root = Import('bsp_root')
    bsppkgs = os.path.join(bsp_root, 'packages')

    conn = get_conn(dbpathname)
    save_sql = '''insert into packagefile values (?, ?, ?)'''
    package = os.path.basename(pkgspathname)
    #print "pathname",pathname
    md5pathname = os.path.join(bsppkgs, pathname)
    md5 = GetFileMd5(md5pathname)
    #print "md5",md5
    data = [(pathname, package, md5)]
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


def remove_unchangedfile(pathname, dbpathname, dbsqlname):
    flag = True

    conn = get_conn(dbpathname)
    c = get_cursor(conn)

    #print 'pathname',pathname
    #print 'dbsqlname',dbsqlname

    filemd5 = GetFileMd5(pathname)
    #print "filemd5:",filemd5
    dbmd5 = 0

    sql = 'SELECT md5 from packagefile where pathname = "' + dbsqlname + '"'
    #print sql
    cursor = c.execute(sql)
    for row in cursor:
        dbmd5 = row[0]  # fetch md5 from databas
    #print "dbmd5:",dbmd5

    if dbmd5 == filemd5:
        # delete file info from database
        sql = "DELETE from packagefile where pathname = '" + dbsqlname + "'"
        cursor = c.execute(sql)
        conn.commit()
        os.remove(pathname)
    else:
        print ("%s has been changed." % pathname)
        print ('Are you sure you want to permanently delete the file: %s?' %
               os.path.basename(pathname))
        print ('If you choose to keep the changed file,you should copy the file to another folder. \nbecaues it may be covered by the next update.')
        rc = raw_input(
            'Press the Y Key to delete the file or just press Enter to keep the file.')
        if rc == 'y' or rc == 'Y':
            sql = "DELETE from packagefile where pathname = '" + dbsqlname + "'"
            cursor = c.execute(sql)
            conn.commit()
            os.remove(pathname)
            print("%s has been removed.\n" % pathname)
        else:
            flag = False
    conn.close()
    return flag


#删除一个包，如果有文件被改动，则提示(y/n)是否要删除，输入y则删除文件，输入其他字符则保留文件。
#如果没有文件被改动，直接删除文件夹,包文件夹被完全删除返回true，有被修改的文件没有被删除返回false
def deletepackdir(dirpath, dbpathname):
    flag = getdirdisplay(dirpath, dbpathname)

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
def displaydir(filepath, basepath, length, dbpathname):
    flag = True
    if os.path.isdir(filepath):
        files = os.listdir(filepath)
        for fi in files:
            fi_d = os.path.join(filepath, fi)
            if os.path.isdir(fi_d):
                displaydir(fi_d, basepath, length, dbpathname)
            else:
                pathname = os.path.join(filepath, fi_d)
                dbsqlname = basepath + os.path.join(filepath, fi_d)[length:]
                #print dbsqlname
                if not remove_unchangedfile(pathname, dbpathname, dbsqlname):
                    flag = False
    return flag


def getdirdisplay(filepath, dbpathname):
    display = filepath
    length = len(display)
    basepath = os.path.basename(filepath)
    #print "basepath:",basepath
    flag = displaydir(filepath, basepath, length, dbpathname)
    return flag
