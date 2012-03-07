"""Respond to do_command target='zigbee'"""

import sys
import thread

# import ElementTree, there are a couple of different places to find it
try:
    from xml.etree import cElementTree as ET
except:
    try:
       from xml.etree import ElementTree as ET
    except:
       import ElementTree as ET


#TODO: only support zigbee if xbee has already been imported by another part of the code?
rci = None
xbee = None

# Should be called from rci and xbee module after import
def connect():
    global rci, xbee
    rci = sys.modules.get('rci')
    xbee = sys.modules.get('xbee')
    if rci and xbee:
        # register callback for zigbee once xbee and rci are imported
        #NOTE: this is a blocking call!
        thread.start_new_thread(rci.add_rci_callback, ('zigbee', zigbee))

def zigbee(rci_data):
    cmd = ET.fromstring(rci_data)
    root = None
    if cmd.tag.strip().lower() == 'discover':
        # get parameters
        start = int(cmd.get('start', '1'))-1 #change to zero index
        size = int(cmd.get('size', '10000')) + start #default to all nodes (shouldn't be more than 10000)
        refresh = cmd.get('option', 'None') == 'clear'
        # request data
        nodes = xbee.get_node_list(refresh=refresh)
        # build response
        root = ET.Element('discover')
        for n in xrange(start, min(size, len(nodes))):
            node = nodes[n]
            device = ET.SubElement(root, 'device')
            device.attrib['index'] = str(n+1) #start index at 1 instead of 0
            ET.SubElement(device, 'type').text = node.type
            ET.SubElement(device, 'ext_addr').text = node.addr_extended[1:-2]+'!' #remove '[' and ']'
            ET.SubElement(device, 'net_addr').text = '0x'+node.addr_short[1:-2]
            ET.SubElement(device, 'mfg_id').text = "0x%04x" % node.manufacturer_id
    
    if root:
        return ET.tostring(root)
    else:
        raise Exception("ZigBee command \"%s\" Not Supported." % cmd.tag.strip())

