# Copyright (c) 2009-2010 Digi International Inc., All Rights Reserved
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

# DEVNOTES
# socket.getfqdn() for my hostname
# socket.inet_ntoa and .inet_aton exist for converting packed 4-byte struct in_addr to/from dotted quad
# socket.getsockname() to get the local address; returns a (host, port) pair

# import ElementTree, there are a couple of different places to find it
try:
    from xml.etree import cElementTree as ET
except:
    try:
       from xml.etree import ElementTree as ET
    except:
       import ElementTree as ET

from simulator_settings import settings

def query_setting():
    root = ET.Element('query_setting')
    # boot
    boot = ET.SubElement(root, 'boot')
    ET.SubElement(boot, 'IP').text = settings.get('my_ipaddress','0.0.0.0')
    ET.SubElement(boot, 'addp').text = 'on'
    # system
    system = ET.SubElement(root, 'system')
    ET.SubElement(system, 'contact').text = settings.get('contact','')
    ET.SubElement(system, 'Location').text = settings.get('location','')
    ET.SubElement(system, 'description').text = settings.get('description','')
    # global management
    mgmtglobal = ET.SubElement(root, 'mgmtglobal')
    ET.SubElement(mgmtglobal, 'deviceId').text = '0x%s' % settings["device_id"].replace("-", "")
    ET.SubElement(mgmtglobal, 'rciCompressionEnabled').text = 'off'
    ET.SubElement(mgmtglobal, 'tcpNodelayEnabled').text = 'off'
    ET.SubElement(mgmtglobal, 'tcpKeepalivesEnabled').text = 'on'
    ET.SubElement(mgmtglobal, 'connIdleTimeout').text = '0'
    ET.SubElement(mgmtglobal, 'dataServiceEnabled').text = 'on'
    ET.SubElement(mgmtglobal, 'dataServicePort').text = '80'
    ET.SubElement(mgmtglobal, 'dataServiceSecurePort').text = '443'
    ET.SubElement(mgmtglobal, 'dataServiceUrl').text = '/ws/device'
    # ADDP
    addp = ET.SubElement(root, 'addp')
    ET.SubElement(addp, 'state').text = 'on'
    ET.SubElement(addp, 'port').text = '2362'
    ET.SubElement(addp, 'desc').text = 'ADDP Service'
    ET.SubElement(addp, 'keepalive').text = 'unsupported'
    ET.SubElement(addp, 'nodelay').text = 'unsupported'
    ET.SubElement(addp, 'delayed_ack').text = '200'
    ET.SubElement(addp, 'reduced_buffer').text = 'off'
    # connection management
    mgmtconnection = ET.SubElement(root, 'mgmtconnection')
    ET.SubElement(mgmtconnection, 'connectionType').text = 'client'
    ET.SubElement(mgmtconnection, 'connectionEnabled').text = 'on'
    ET.SubElement(mgmtconnection, 'lastKnownAddressUpdateEnabled').text = 'off'
    ET.SubElement(mgmtconnection, 'clientConnectionReconnectTimeout').text = '300'
    serverArray = ET.SubElement(mgmtconnection, 'serverArray')
    ET.SubElement(serverArray, 'serverAddress').text = 'en://'+settings['idigi_server']
    ET.SubElement(serverArray, 'securitySettingsIndex').text = '0'
    # network management?
    return ET.tostring(root)

