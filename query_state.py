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

import sys
import struct
try:
    from xml.etree import cElementTree as ET
except:
    try:
       from xml.etree import ElementTree as ET
    except:
       import ElementTree as ET
from simulator_settings import settings

# Zigbee State capability 0x200 required for Digi X-Grid/Open EMS 
def query_state():
    xbee = sys.modules.get('xbee')

    root = ET.Element('query_state')
    # device_info
    device_info = ET.SubElement(root, 'device_info')
    ET.SubElement(device_info, 'mac').text = '0:0:0:0:0:0' #TODO: get this from the PC or settings file.
    ET.SubElement(device_info, 'product').text = settings['product']
    ET.SubElement(device_info, 'company').text = settings['company']
    #TODO: we could add firmware and other version information here...
    # boot_stats
    boot_stats = ET.SubElement(root, 'boot_stats')
    ET.SubElement(boot_stats, 'ip').text = settings.get('ipaddress','0.0.0.0')
    ET.SubElement(boot_stats, 'addp').text = 'on'
    # zigbee_state
    if xbee:   
        zigbee_state = ET.SubElement(root, 'zigbee_state')
        ET.SubElement(zigbee_state, 'gateway_addr').text = ':'.join(["%02x" % ord(x) for x in xbee.ddo_get_param(None, 'SH')+xbee.ddo_get_param(None, 'SL')])
        ET.SubElement(zigbee_state, 'pan_id').text = '0x%04x' % struct.unpack('>H', xbee.ddo_get_param(None, 'OI'))
        ET.SubElement(zigbee_state, 'ext_pan_id').text = '0x%x' % struct.unpack('>Q', xbee.ddo_get_param(None, 'ID')) # ''.join(["%02x" % ord(x) for x in xbee.ddo_get_param(None, 'ID')])
        ET.SubElement(zigbee_state, 'channel').text = '0x%x' % ord(xbee.ddo_get_param(None, 'ch'))
        ET.SubElement(zigbee_state, 'net_addr').text = '0x%04x' % struct.unpack('>H', xbee.ddo_get_param(None, 'MY'))
        ET.SubElement(zigbee_state, 'association').text = '0x%x' % ord(xbee.ddo_get_param(None, 'AI'))
        ET.SubElement(zigbee_state, 'firmware_version').text = '0x%04x' % struct.unpack('>H', xbee.ddo_get_param(None, 'VR')) 
        ET.SubElement(zigbee_state, 'hardware_version').text = '0x%04x' % struct.unpack('>H', xbee.ddo_get_param(None, 'HV'))
        ET.SubElement(zigbee_state, 'children').text = '%d' % ord(xbee.ddo_get_param(None, 'NC'))
        ET.SubElement(zigbee_state, 'max_payload').text = '%d' % struct.unpack('>H', xbee.ddo_get_param(None, 'NP'))
        try:
            ET.SubElement(zigbee_state, 'verify_cert').text = '%d' % ord(xbee.ddo_get_param(None, 'VC'))
        except:
            pass #only valid for SE XBees
        ET.SubElement(zigbee_state, 'stack_profile').text = '%d' % ord(xbee.ddo_get_param(None, 'ZS'))
    
    return ET.tostring(root)
