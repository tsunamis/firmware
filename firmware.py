import sys
import re
import time
import ssl    
import json
import argparse
if sys.version_info.major == 2:
    import urllib2
else:
    import urllib.parse
    import urllib.request
import datetime
from bs4 import BeautifulSoup

firmwares = []
branch = 'v1.1.5'
uri = 'https://anglerfish.ignitenet.com:58180/archive/dev2/SS-AC1900_branch/'
uri = 'https://anglerfish.ignitenet.com:58180/archive/dev2/SS-AC1900/'
user = 'change-me'
passwd = 'change-me'

if len(sys.argv) < 3:
    print(sys.argv)
    print('example #1: python firmware.py v1.1.5 https://anglerfish.ignitenet.com:58180/archive/dev2/SF-AC1200/')
    print('example #2: python firmware.py v1.1.5 https://anglerfish.ignitenet.com:58180/archive/dev2/SS-AC1200/')
    print('example #3: python firmware.py v1.1.5 https://anglerfish.ignitenet.com:58180/archive/dev2/SS-AC1900/')
    print('example #4: python firmware.py v1.1.6 https://anglerfish.ignitenet.com:58180/archive/dev3/MetroLinq/')
    sys.exit(254)

branch = str(sys.argv[1])
uri = str(sys.argv[2])

def get_resource(uri='', user='', passwd=False):
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    if sys.version_info.major == 2:
        password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()

        password_mgr.add_password(None, uri, user, passwd)

        auth_handler = urllib2.HTTPBasicAuthHandler(password_mgr)

        opener = urllib2.build_opener(auth_handler, urllib2.HTTPSHandler(context=context))

        urllib2.install_opener(opener)

        return urllib2.urlopen(uri).read()


    # Else
    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()

    password_mgr.add_password(None, uri, user, passwd)

    auth_handler = urllib.request.HTTPBasicAuthHandler(password_mgr)

    opener = urllib.request.build_opener(auth_handler, urllib.request.HTTPSHandler(context=context))

    urllib.request.install_opener(opener)

    return urllib.request.urlopen(uri).read()



def return_date(ts):
    return datetime.datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')


html = get_resource(uri, user, passwd)
soup = BeautifulSoup(html, 'html.parser')


for row in soup.find_all('tr'):
    f = []
    for cell in row("td"):
        f.append(cell.text)

    firmware = {}
    if len(f) == 4:
        try:
            d = datetime.datetime.strptime(f[1], '%Y-%b-%d %H:%M:%S')
            dtt = d.timetuple()

            match = re.search(r'v\d.\d.\d', f[0])
            if match:
                firmware['branch'] = match.group()

                firmware['timestamp'] = time.mktime(dtt)
                firmware['bin'] = f[0]
                firmware['path'] = uri+f[0]

                firmwares.append(firmware)
        except ValueError:
            pass

by_branch = [ (i['timestamp'], i['path'], i['bin']) for i in firmwares if i['branch'] == branch ]

if len(by_branch) > 0:
    oldest = min(by_branch, key = lambda t: t[0])
    newest = max(by_branch, key = lambda t: t[0])

    #print(return_date(oldest[0]), oldest[2])
    print(return_date(newest[0]), newest[2])

    f=open(newest[2], "wb")
    f.write(get_resource(newest[1], user, passwd))
else:
    print("No match")
    sys.exit(255)
