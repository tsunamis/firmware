#!/usr/bin/env python

import socket
import sys
import re
import time
import ssl    
import json
import argparse
import paramiko
from ConfigParser import ConfigParser
import scp
if sys.version_info.major == 2:
    import urllib2
else:
    import urllib.parse
    import urllib.request
import datetime
from bs4 import BeautifulSoup
try:
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import as_completed as future_completed
except ImportError as e:
    print "please run 'pip install --user futures'"



config_file = 'link.cfg'

config = ConfigParser()
config.readfp(open(config_file))



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


def beautifier(soup, uri):
    firmwares = []
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
    return firmwares


def device_firmwares(user, passwd, uri, branch = 'v1.1.5'):
    html = get_resource(uri, user, passwd)
    soup = BeautifulSoup(html, 'html.parser')
    firmwares = beautifier(soup, uri)
    by_branch = [ (i['timestamp'], i['path'], i['bin']) for i in firmwares if i['branch'] == branch ]

    return by_branch

def make_connect(ip, port, user, passwd, num_retries = 6):
    retry = 1
    while retry < num_retries:
        #print("Trying on "+str(ip)+" times: "+str(retry))
        try:
            con = paramiko.SSHClient()
            con.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            con.connect(ip, port, user, passwd)
            return con

        except (paramiko.BadHostKeyException, paramiko.AuthenticationException, paramiko.SSHException, socket.error, EOFError) as e:
            print(e)
            time.sleep(5)
            retry += 1


        #except socket.error, (value, message):
        #    if value in (51, 61, 110, 111):
        #        print('SSH Connection refused, will retry in 5 seconds')
        #        time.sleep(5)
        #        retry += 1
        #    else:
        #        raise

        #except paramiko.AuthenticationException, e:
        #    print(ip+' Authentication Error')
        #    break

        #except EOFError:
        #    print('Unexpected Error from SSH Connection, retry in 5 seconds')
        #    time.sleep(5)
        #    retry += 1

    print('Could not establish SSH connection to '+ip) 
    return None


def upload(ip, port, user, passwd, source, destination = '/tmp/fw.bin', upgrade = False):
    con = make_connect(ip, port, user, passwd)
    if con:
        #con = paramiko.SSHClient()
        #con.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        #con.connect(ip, port = port, username = user, password = passwd)

        pipe = scp.SCPClient(con.get_transport())
        pipe.put(source, destination)       


        if upgrade:
            CMD = "sh -c '/sbin/sysupgrade -c /tmp/fw.bin > /dev/null 2>&1 &'"
            stdin, stdout, stderr = con.exec_command(CMD)
            #print(stdout.readlines())

        # Debuginimo tikslais
        #CMD = "reboot"
        #stdin, stdout, stderr = con.exec_command(CMD)

        con.close()
        return True

    else:
        print("Unsusccesfull make connection on "+ip)
        return False





def job(d):
    wusername = config.get("anglerfish", "username")
    wpassword = config.get("anglerfish", "password")

    username = config.get(d, "username")
    password = config.get(d, "password")
    ip = config.get(d, "ip")
    port = int(config.get(d, "port"))
    uri = config.get(d, "uri")
    device = config.get(d, "device")
    branch = config.get(d, "branch")

    # Return firmware by branch
    by_branch = device_firmwares(wusername, wpassword, uri, branch = branch)

    if len(by_branch) == 0:
        print('No firmware found on '+ip)
        return False

    # Return newest firmware
    newest = max(by_branch, key = lambda t: t[0])

    # Download firmware
    file_name = '/tmp/'+d+'_'+device+'.bin'
    url = newest[1]
    f=open(file_name, "wb")                                                                                                                                                               
    f.write(get_resource(url, wusername, wpassword)) 

    # Upload firmware
    if not upload(ip, port, username, password, file_name, upgrade = True):
        return False


    time.sleep(30)


    # Check if susccesfull upgraded 
    # Pagal ideja jau cia netur ibuti connection'o
    con = make_connect(ip, port, username, password, num_retries = 25)
    if not con:
        return False

    CMD = "cat /etc/version"
    stdin, stdout, stderr = con.exec_command(CMD)
    device_firmware = stdout.readlines()[0].rstrip('\n')
    print("Pasiziurejau versija")
    print(device_firmware+" "+newest[2])

    return True


with ThreadPoolExecutor(max_workers=3) as executor:

    result = []
    jobs = []
    for d in ['td','gd1', 'gd2']:
        jobs.append(executor.submit(job, d))

    for future in future_completed(jobs):
        try:
            data = future.result()
            result.append(data)
        except Exception as e:
            raise e

if all(result) == False:
    sys.exit(255)

print("Everything OK")
