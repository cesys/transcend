#!/usr/bin/python2.7
#
# Transcend client
#

import argparse
import atexit
import json
import os
import random
import shutil
import smb
import socket

from smb.SMBConnection import SMBConnection
from cStringIO import StringIO

username        = 'GUEST'                   # Username
password        = ''                        # Password
ports           = [2001, 445]               # can be 2000 or 445 to avoid firewalls
client_name     = 'testclient'              # Usually safe to use 'testclient'
server_name     = 'TRANSCEND'               # Must match the NetBIOS name of the remote server
server_ip       = '172.31.130.110'          # Must point to the correct IP address
domain_name     = ''                        # Safe to leave blank, or fill in the domain used for your remote server
shared_folder   = 'transcend'               # Set to the shared folder name
index_filename  = '.index'                  # Index filename
tmp_folder      = '/tmp/.transcend'         # Temporary folder
server_path     = ''                        # Path for transcend files in the server
verbose         = False                     # Verbose flag
key_length      = 8                         # Key lenght
key_set         = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"       # Key set

def check_key(key):
    if len(key) != key_length:
        return False
    for c in key:
        if c not in key_set:
            return False
    return True

def generate_key():
    return ''.join(random.choice(key_set) for n in xrange(key_length))

def connect():
    conn = SMBConnection(username, password, client_name, server_name, domain=domain_name, use_ntlm_v2=True,
                         is_direct_tcp=True)
    for port in ports:
        try:
            if conn.connect(server_ip, port):
                break
        except socket.timeout:
            print "Socket timeout: samba protocol is not responding on port " + port
    return conn

def download(conn, path, filename, dest, service_name):
    if conn:
        if verbose: print 'Download = ' + path + filename
        try:
            attr = conn.getAttributes(service_name, path + filename)
            if verbose: print 'Size = %.1f kB' % (attr.file_size / 1024.0)
            if verbose: print 'Start download'
            file_obj = StringIO()
            file_attributes, filesize = conn.retrieveFile(service_name, path + filename, file_obj)
            fw = open(dest, 'w')
            file_obj.seek(0)
            for line in file_obj:
                fw.write(line)
            fw.close()
            if verbose: print 'Download finished'
            return True
        except smb.smb_structs.OperationFailure:
            if verbose: print "File " + path + filename + " doesn't exists."
            return False


def upload(conn, path, filename, source, service_name):
    if conn:
        if verbose: print 'Upload = ' + path + filename
        if verbose: print 'Size = %.1f kB' % (os.path.getsize(filename) / 1024.0)
        if verbose: print 'Start upload'
        with open(source, 'r') as file_obj:
            filesize = conn.storeFile(service_name, path + filename, file_obj)
        if verbose: print 'Upload finished'

def loadindex(conn):
    index_path_filename = tmp_folder + "/" +index_filename
    index = {}
    if download(conn, server_path, index_filename, index_path_filename, shared_folder):
        index = json.load(open(index_path_filename))
    return index

def saveindex(conn, index):
    index_path_filename = tmp_folder + "/" + index_filename
    with open(index_path_filename, 'w') as outfile:
        json.dump(index, outfile)
    upload(conn, server_path, index_filename, index_path_filename, shared_folder)

def upload_file(args):
    conn = connect()
    try:
        index = loadindex(conn)
        while True:
            key = generate_key()
            if key not in index.keys():
                break
        print 'Uploading file ' + args.key +  "..."
        try:
            upload(conn, server_path, key, args.key, shared_folder)
        except IOError:
            print "Cannot retrieve file " + args.key
            return
        data = dict()
        data["filename"] = args.key
        index[key] = data
        saveindex(conn, index)
        print "Done."
        print "Transcend key: " + key
    finally:
        conn.close()

def download_file(args):
    conn = connect()
    try:
        if not check_key(args.key):
            print "Malformed key!"
            return
        index = loadindex(conn)
        if args.key in index.keys():
            filename = index[args.key]["filename"]
            print 'Downloading file ' + filename + " ..."
            if not download(conn, server_path, args.key, filename, shared_folder):
                print "Cannot retrieve file. Datastore corrupted."
                return
        else:
            print "Key " + args.key + " doesn't exist in the datastore."
            return
        saveindex(conn, index)
        print "Done."
    finally:
        conn.close()

def init(args):
    if not os.path.exists(tmp_folder):
        os.makedirs(tmp_folder)

def dispatch(args):
    global verbose
    verbose = args.verbose
    if args.upload:
        upload_file(args)
    else:
        download_file(args)

def exit_handler():
    # Dispose resources
    if os.path.exists(tmp_folder):
        shutil.rmtree(tmp_folder)

def main():
    atexit.register(exit_handler)
    parser = argparse.ArgumentParser(description='Transcend is a tool to upload/download files '
                                                 'to/from a server through a simple ID in a transparent way')
    parser.add_argument('key', type=str,
                        help='transcend key or filename')
    parser.add_argument('-u', '--upload', dest='upload', action='store_true', default=False,
                        help='upload file')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', default=False,
                        help='verbose')

    args = parser.parse_args()
    init(args)
    dispatch(args)


if __name__ == "__main__":
    main()