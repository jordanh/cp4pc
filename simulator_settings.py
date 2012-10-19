#
# Copyright (c) 2009-2012 Digi International Inc.
# All rights not expressly granted are reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.
# 
# Digi International Inc. 11001 Bren Road East, Minnetonka, MN 55343
#
__version__ = "1.6.0"

# this file stores the settings from the command line arguments.
import uuid
import json
import os

def _decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv

def _decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = _decode_dict(value)
        rv[key] = value
    return rv        

class SettingsDict(dict):
    def __init__(self, filename):
        self.filename = filename
        self.callbacks = {} # key: [callbacks]
        # initialize dict from file
        if os.path.isfile(self.filename):
            fp = open(self.filename, 'r')
            try:
                # The object_hook is used to translate the unicode strings into utf-8 strings
                return dict.__init__(self, json.load(fp, object_hook=_decode_dict))
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
settings.setdefault('com_port', '') #default to empty string
settings.setdefault('baud', 115200) #should the default be 9600?

# iDigi Settings
# base the device ID on the MAC address (can be overwritten after import)
settings.setdefault('device_id', "00000000-00000000-%06XFF-FF%06X" % ((settings.get('mac', 0x000000000000) & 0xFFFFFF000000) >> (8*3), 
                                                                       settings.get('mac', 0x000000000000) & 0x0000000FFFFFF))
settings.setdefault('idigi_server', 'my.idigi.com')
settings.setdefault('idigi_certs_file', 'idigi-ca-cert-public.crt')
settings.setdefault('device_type', 'PC Gateway')
#settings.setdefault('vendor_id', 0x0) #can set vendor ID in iDigi

# extra descriptions
settings.setdefault('company', 'Digi International') 
#settings.setdefault('device_name', '') # user friendly name for the device
#settings.setdefault('contact', 'name@example.com')
#settings.setdefault('location', 'SomewhereVille, USA')
#settings.setdefault('description', 'My lovely PC Gateway')

# If local_port is set, start a webserver for processing RCI and HTML requests locally
#settings.setdefault('local_port', 8080)

# Firmware version to report to iDigi.
# aa.bb.cc.dd. Convert each section to hex, concatenate, convert to int.
#settings.setdefault('firmware_version', 16777216) # 1.0.0.0 
