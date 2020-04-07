# -*- coding:utf-8 -*-
#
# File      : package.py
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
# 2018-12-28     Ernest Chen     Add package information and enjoy package maker
# 2020-4-7       SummerGift      Code improvement
#

import os
import json
import archive
import sys
import requests

"""Template for creating a new file"""

Bridge_SConscript = '''import os
from building import *

objs = []
cwd  = GetCurrentDir()
list = os.listdir(cwd)

for item in list:
    if os.path.isfile(os.path.join(cwd, item, 'SConscript')):
        objs = objs + SConscript(os.path.join(item, 'SConscript'))

Return('objs')
'''

Kconfig_file = '''
# Kconfig file for package ${lowercase_name}
menuconfig PKG_USING_${name}
    bool "${description}"
    default n

if PKG_USING_${name}

    config PKG_${name}_PATH
        string
        default "/packages/${pkgs_class}/${lowercase_name}"

    choice
        prompt "Version"
        default PKG_USING_${name}_LATEST_VERSION
        help
            Select the package version

        config PKG_USING_${name}_V${version_standard}
            bool "v${version}"

        config PKG_USING_${name}_LATEST_VERSION
            bool "latest"
    endchoice
          
    config PKG_${name}_VER
       string
       default "v${version}"    if PKG_USING_${name}_V${version_standard}
       default "latest"    if PKG_USING_${name}_LATEST_VERSION

endif

'''

Package_json_file = '''{
  "name": "${name}",
  "description": "${description}",
  "description_zh": "${description_zh}",  
  "enable": "PKG_USING_${pkgs_using_name}", 
  "keywords": [
    "${keyword}"
  ],
  "category": "${pkgsclass}",
  "author": {
    "name": "${authorname}",
    "email": "${authoremail}",
    "github": "${authorname}"
  },
  "license": "${license}",
  "repository": "${repository}",
  "icon": "unknown",
  "homepage": "unknown",
  "doc": "unknown",
  "site": [
    {
      "version": "v${version}",
      "URL": "https://${name}-${version}.zip",
      "filename": "${name}-${version}.zip",
      "VER_SHA": "fill in the git version SHA value"
    },
    {
      "version": "latest",
      "URL": "https://xxxxx.git",
      "filename": "Null for git package",
      "VER_SHA": "fill in latest version branch name, such as master"
    }
  ]
}
'''

Sconscript_file = '''
from building import *

cwd     = GetCurrentDir()
src     = Glob('*.c') + Glob('*.cpp')
CPPPATH = [cwd]

group = DefineGroup('${name}', src, depend = [''], CPPPATH = CPPPATH)

Return('group')
'''


class Package:
    pkg = None

    def parse(self, filename):
        with open(filename, "r") as f:
            json_str = f.read()

        if json_str:
            self.pkg = json.loads(json_str)

    def get_name(self):
        return self.pkg['name']

    def get_filename(self, ver):
        for item in self.pkg['site']:
            if item['version'].lower() == ver.lower():
                return item['filename']

        return None

    def get_url(self, ver):
        for item in self.pkg['site']:
            if item['version'].lower() == ver.lower():
                return item['URL']

        return None

    def get_versha(self, ver):
        for item in self.pkg['site']:
            if item['version'].lower() == ver.lower():
                return item['VER_SHA']

        return None

    def get_site(self, ver):
        for item in self.pkg['site']:
            if item['version'].lower() == ver.lower():
                return item

        return None

    def download(self, ver, path, url_from_srv):
        ret = True
        url = self.get_url(ver)
        site = self.get_site(ver)
        if site and 'filename' in site:
            filename = site['filename']
            path = os.path.join(path, filename)
        else:
            basename = os.path.basename(url)
            path = os.path.join(path, basename)

        if os.path.isfile(path):
            if not os.path.getsize(path):
                os.remove(path)
            else:
                if archive.packtest(path):
                    # print "The file is rigit."
                    return True
                else:
                    os.remove(path)

        retry_count = 0

        headers = {'Connection': 'keep-alive',
                   'Accept-Encoding': 'gzip, deflate',
                   'Accept': '*/*',
                   'User-Agent': 'curl/7.54.0'}

        print('Start to download package : %s ' % filename.encode("utf-8"))

        while True:
            # print("retry_count : %d"%retry_count)
            try:
                r = requests.get(url_from_srv, stream=True, headers=headers)

                flush_count = 0

                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                            f.flush()
                        flush_count += 1
                        sys.stdout.write("\rDownloding %d KB" % flush_count)
                        sys.stdout.flush()

                retry_count = retry_count + 1

                if archive.packtest(path):  # make sure the file is right
                    ret = True
                    print("\rDownloded %d KB  " % flush_count)
                    print('Start to unpack. Please wait...')
                    break
                else:
                    if os.path.isfile(path):
                        os.remove(path)
                    if retry_count > 5:
                        print(
                            "error: Have tried downloading 5 times.\nstop Downloading file :%s" % path)
                        if os.path.isfile(path):
                            os.remove(path)
                        ret = False
                        break
            except Exception as e:
                print(url_from_srv)
                print('error message:%s\t' % e)
                retry_count = retry_count + 1
                if retry_count > 5:
                    print('%s download fail!\n' % path.encode("utf-8"))
                    if os.path.isfile(path):
                        os.remove(path)
                    return False
        return ret

    @staticmethod
    def unpack(package_path, path, pkg, package_name_in_json):
        try:
            # ignore the return value
            archive.unpack(package_path, path, pkg, package_name_in_json)
            return True
        except Exception as e:
            print('unpack error message :%s' % e)
            print('unpack %s failed' % os.path.basename(package_path))
            os.remove(package_path)
            return False
