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
"""Respond to do_command target='zigbee'"""
from rci.model.base import BranchNode, TargetNode, LeafNode, DTYPE, RCIAttribute
import sys

# import ElementTree, there are a couple of different places to find it
try:
    from xml.etree import cElementTree as ET
except:
    try:
        from xml.etree import ElementTree as ET
    except:
        import ElementTree as ET

xbee = None #global XBee module set by ZigbeeTarget

#TODO: move this to a utility file?
def binstring_to_uint(value):
    retval = 0
    #eat string starting from the first (most significant) byte
    for curr_byte in value:
        retval = retval * 256 + ord(curr_byte)
    return retval

def xbee_enabled():
    global xbee
    if xbee is None:
        xbee = sys.modules.get('xbee', sys.modules.get('xbee'))
    return xbee is not None

class ZigbeeTarget(TargetNode):
    desc = "Interact with the XBee radio on the device."
    
    def __init__(self, root_fs="."):
        TargetNode.__init__(self, "zigbee")
        # include the ZigBee commands
        self.attach(Discover())
        self.attach(QuerySetting())
        self.attach(QueryState())

    def descriptor_xml(self, xml_node):
        # only process requests if xbee or zigbee module has been imported by the code.
        if xbee_enabled():
            return TargetNode.descriptor_xml(self, xml_node)
        else:
            return ''
        
    def handle_xml(self, xml_tree):
        # only process requests if xbee or zigbee module has been imported by the code.
        #TODO: make sure code doesn't skip this class and access child classes directly
        if xbee_enabled():
            return TargetNode.handle_xml(self, xml_tree)
        else:
            return ''


class Discover(BranchNode):
    desc = "Discover nodes on XBee network and return numbered list of nodes."
    errors = {
        1: "Sub-element not allowed under discover",
        2: "Parameter error",
        3: "Command error",
        4: "Node not found",
    }

    TYPE_CONVERSION = {'coordinator': '0',
                       'router': '1',
                       'end': '2'}

    def __init__(self):
        BranchNode.__init__(self, 'discover')
        # TODO: add children nodes?
    
    def handle_xml(self, discover_element):
        # get parameters
        try:
            start = int(discover_element.get('start', '1'))-1 #change to zero index
            size = int(discover_element.get('size', '10000')) + start #default to all nodes (shouldn't be more than 10000)
            refresh = discover_element.get('option', 'None') == 'clear'
        except Exception, e:
            return self._xml_error(2, hint=str(e)) #parameter error
        
        # request data
        try:
            if xbee_enabled():
                nodes = xbee.get_node_list(refresh=refresh)
            else:
                return self._xml_error(5, 'XBee not found.')
        except Exception, e:
            return self._xml_error(3, hint='get_node_list failed.')
        
        # build response
        root = ET.Element('discover')
        for n in xrange(start, min(size, len(nodes))):
            node = nodes[n]
            device = ET.SubElement(root, 'device')
            device.attrib['index'] = str(n+1) #start index at 1 instead of 0
            ET.SubElement(device, 'type').text = self.TYPE_CONVERSION.get(node.type, '0')
            ET.SubElement(device, 'ext_addr').text = node.addr_extended[1:-2].lower()+'!' #remove '[' and ']'
            ET.SubElement(device, 'net_addr').text = '0x'+node.addr_short[1:-2].lower()
            ET.SubElement(device, 'parent_addr').text = '0x'+node.addr_parent[1:-2].lower()
            if node.addr_extended.lower().startswith('[00:13:a2'):
                # this is an XBee, let's default these parameters
                ET.SubElement(device, 'profile_id').text = '0xc105'
                ET.SubElement(device, 'mfg_id').text = '0x101e'
            else:
                ET.SubElement(device, 'profile_id').text = '0x%04x' % node.profile_id
                ET.SubElement(device, 'mfg_id').text = "0x%04x" % node.manufacturer_id                
            ET.SubElement(device, 'device_type').text = '0x000000'
            ET.SubElement(device, 'node_id').text = node.label
            ET.SubElement(device, 'contact_time').text = '0'
        return ET.tostring(root)

    #TODO: fill in descriptor details for discovery command.
    #NOTE: not necessary for iDigi integration.
    #def descriptor_xml(self, xml_node):

class QuerySetting(BranchNode):
    desc = "Request current XBee node configuration"
    errors = {
        1: "Element not allowed under query command",
        2: "Element not allowed under field element",
        3: "Parameter error",
    }

    def __init__(self):
        BranchNode.__init__(self, "query_setting")
        #self.attrs['addr'] = RCIAttribute("addr", "Extended address of node (default is gateway XBee)")#, type="xbee_ext_addr")
        radio = BranchNode("radio", "XBee radio parameters")
        self.attach(radio)
        radio.attach(ATLeafNode('channel', 'CH', DTYPE.xHEX32, 'Operating channel', 10, 26))


class QueryState(BranchNode):
    desc = "Request current XBee node state"
    errors = {
        1: "Element not allowed under query command",
        2: "Element not allowed under field element",
        3: "Parameter error",
    }

    def __init__(self):
        BranchNode.__init__(self, "query_state")
        #self.attrs['addr'] = RCIAttribute("addr", "Extended address of node (default is gateway XBee)")#, type="xbee_ext_addr")
        radio = BranchNode("radio", "XBee radio parameters")
        self.attach(radio)
        radio.attach(ATLeafNode('channel', 'CH', DTYPE.xHEX32, 'Operating channel', 10, 26))    


class ATLeafNode(LeafNode):
    
    def __init__(self, name, at_cmd, dtype=None, desc=None, dmin=None, dmax=None, units=None):
        LeafNode.__init__(self, name)
        self.alias = at_cmd
        if dtype is not None:
            self.dtype = dtype
        if desc is not None:
            self.desc = desc
        self.dmin = dmin
        self.dmax = dmax
        self.units = units
        
    def toxml(self, attributes=None):
        addr = attributes.get('addr') #Will default to own device (None)
        
        if not xbee_enabled():
            return self._xml_error(4, 'XBee not found.')
        
        value = xbee.ddo_get_param(addr, self.alias)
        body = None
        if self.alias.upper() == 'NI':
            # NI is a string, send directly
            body = value
        elif self.dtype in [DTYPE.STRING, DTYPE.HEX32, DTYPE.xHEX32, DTYPE.UINT32]:
            #NOTE: string is used for values that are larger than 32 bits (ugh)
            number = binstring_to_uint(value)
            if self.dtype == DTYPE.UINT32:
                # these are all returned as a number in base 10
                body = str(number)
            else:
                # these are all returned with format 0x... in base 16
                body = "0x%0X" % number
        else:
            pass # body = None, which is what we want
        return self._xml_tag(body)

#class SetSetting(BranchNode):


#class FW_Update(BranchNode):
#class GetLQI(BranchNode):


    
