import os
import json
import archive
import sys

class Package:
    pkg = None

    def parse(self, filename):
        f = file(filename)
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
        import requests
        from clint.textui import progress

        #url = self.get_url(ver)

        site = self.get_site(ver)
        if site and site.has_key('filename'):
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
                    #print "the file is rigit do not need to download"
                    return True
                else:
                    os.remove(path)

        retryCount = 0

        headers = {'Connection': 'keep-alive',
                   'Accept-Encoding': 'gzip, deflate',
                   'Accept': '*/*',
                   'User-Agent': 'curl/7.54.0'}

        #print("download from server:" + url_from_srv)

        print('Start to download package : %s '%filename)

        while True:
            #print("retryCount : %d"%retryCount)
            try:
                r = requests.get(url_from_srv, stream=True, headers=headers)

                flush_count = 0

                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                            f.flush()
                        flush_count += 1
                        sys.stdout.write("\rDownloding %d KB"%flush_count)
                        sys.stdout.flush()

                retryCount = retryCount + 1
                if archive.packtest(path):  # make sure the file is right
                    ret = True
                    print("\rDownloded %d KB  "%flush_count)
                    print('Start to unpack. Please wait...')
                    break
                else:
                    if os.path.isfile(path):
                        os.remove(path)
                    if retryCount > 5:
                        print("error: Have tried downloading 5 times.\nstop Downloading file", path)
                        if os.path.isfile(path):
                            os.remove(path)
                        ret = False
                        break
            except Exception, e:
                #print url_from_srv
                retryCount = retryCount + 1
                if retryCount > 5:
                    print(path, 'download fail!')
                    if os.path.isfile(path):
                        os.remove(path)
                    return False
        return ret

    def unpack(self, fullpkg_path, path):
        try:
            archive.unpack(fullpkg_path, path)
        except Exception, e:
            print('unpack %s failed' % os.path.basename(fullpkg_path)) 
