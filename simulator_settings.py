# Copyright (c) 2009-2012 Digi International Inc., All Rights Reserved
# 
# This software contains proprietary and confidential information of Digi
# International Inc.  By accepting transfer of this copy, Recipient agrees
# to retain this software in confidence, to prevent disclosure to others,
# and to make no use of this software other than that for which it was
# delivered.  This is an published copyrighted work of Digi International
# Inc.  Except as permitted by federal law, 17 USC 117, copying is strictly
# prohibited.
# 
# Restricted Rights Legend
#
# Use, duplication, or disclosure by the Government is subject to
# restrictions set forth in sub-paragraph (c)(1)(ii) of The Rights in
# Technical Data and Computer Software clause at DFARS 252.227-7031 or
# subparagraphs (c)(1) and (2) of the Commercial Computer Software -
# Restricted Rights at 48 CFR 52.227-19, as applicable.
#
# Digi International Inc. 11001 Bren Road East, Minnetonka, MN 55343

__version__ = "1.6.0"

# this file stores the settings from the command line arguments.
import uuid
import json
import os

class SettingsDict(dict):
    def __init__(self, filename):
        self.filename = filename
        self.callbacks = {} # key: [callbacks]
        # initialize dict from file
        if os.path.isfile(self.filename):
            fp = open(self.filename, 'r')
            try:
                return dict.__init__(self, json.load(fp))
            except:
                pass
            finally:
                fp.close()
        return dict.__init__(self)    
    
    def add_callback(self, key, callback):
        # callback should accept the following parameters (new_value, old_value)
        call_list = self.callbacks.setdefault(key, [])
        if callback not in call_list:
            call_list.append(callback)

    def remove_callback(self, key, callback):
        call_list = self.callbacks.get(key)
        if call_list and callback in call_list:
            call_list.remove(callback)
    
    def __setitem__(self, key, new_value):
        original_value = self.get(key)
        # set the new value
        dict.__setitem__(self, key, new_value)
        # make sure the value has changed
        if new_value != original_value:
            # write new settings out to file
            self.write_to_file()
            # call any associated callbacks
            for callback in self.callbacks.get(key, []):
                try:
                    callback(new_value, original_value)
                except:
                    pass
    
    def write_to_file(self):
        fp = open(self.filename, 'w')
        try:
            json.dump(self, fp)
        finally:
            fp.close() 
        

settings = SettingsDict('settings.json')
# example and defaulted Settings

# Settings from computer
if 'mac' not in settings:
    # this function call can be expensive, only call it if need be
    settings['mac'] = uuid.getnode() # get a hardware mac from PC to use as a MAC address

# Program settings
settings.setdefault('version', "0.0.0") #I'd recommend keeping this format

# serial port settings for XBee
settings.setdefault('com_port', 'COM6') #default to first serial port.
settings.setdefault('baud', 115200) #should the default be 9600?

# iDigi Settings
# base the device ID on the MAC address (can be overwritten after import)
settings.setdefault('device_id', "00000000-00000000-%06XFF-FF%06X" % ((settings.get('mac', 0x000000000000) & 0xFFFFFF000000) >> (8*3), 
                                                                       settings.get('mac', 0x000000000000) & 0x0000000FFFFFF))
settings.setdefault('idigi_server', 'developer.idigi.com')
settings.setdefault('idigi_certs_file', 'idigi-ca-cert-public.crt')
settings.setdefault('device_type', 'PC Gateway')
#settings.setdefault('vendor_id', 0x12345678) #can set vendor ID in iDigi

# extra descriptions
settings.setdefault('company', 'Digi International') 
#settings.setdefault('device_name', '') # user friendly name for the device
#settings.setdefault('contact', 'name@example.com')
#settings.setdefault('location', 'SomewhereVille, USA')
#settings.setdefault('description', 'My lovely PC Gateway')

# If local_port is set, start a webserver for processing RCI and HTML requests locally
#settings.setdefault('local_port', 8080)
