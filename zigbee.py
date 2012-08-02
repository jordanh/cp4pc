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


# WARNING: 
#
# This library is not officially supported and is provided for testing
# purposes.  Use at your own risk.

# Requirements:
# Must have pySerial and associated libraries (win32 module for Windows)
# Serial connection to XBee must be configured in simulator_settings ('com_port' and 'baud').
# XBee must be API mode firmware.  ZB, ZNet2.5 or Smart Energy.

# Limitations:
# Must import zigbee before doing either "from socket import *" or "from select import *"
# Must import zigbee to use zigbee socket.
# Must import zigbee to use zigbee select.
# Zigbee socket options not support (except non_blocking)
# Incomplete error checking.
# Anything else not implemented from the TODO list below.

# TODO List:
#    Add socket options (mostly counters needed).
#    Check message size before sending (could split into multiple messages).
#    Add more error checking and match ConnectPort errors
#    Support for blocking calls for sendto
#    Add new parameters to getnodelist, ddo_get_param, ddo_set_param

import struct
import string
import time
import socket
import select
import logging
from threading import RLock

# set up logger
logger = logging.getLogger("cp4pc.xbee")
logger.setLevel(logging.INFO)

MESH_TRACEBACK = False
"Set this to true to enable printing of all ZigBee traffic"

# set parameters
__all__ = ["ddo_get_param", "ddo_set_param", "getnodelist", "get_node_list", "register_joining_device"]

# Globals
"Set this to function that accepts string to get passed MESH_TRACEBACK data"
debug_callback = None
com_port_opened = False #set to True when the COM port has been successfully opened (see bottom of this file)
# PySerial calls will need to be protected from multiple threads:
_global_lock = RLock()
# A lock used to manage the com-port management threads:
_com_mgmt_lock = RLock()

def __register_with_socket_module(object_name):
    "Register object with socket module (add to __all__)"
    try:
        if socket.__all__ is not None:
            if object_name not in socket.__all__:
                socket.__all__.append(object_name)
    except:
        # there is no __all__ defined for socket object
        pass

def MAC_to_address_string(MAC_address, num_bytes = 8):
    """Convert a MAC address to a string with "[" and "]" """
    address_string = "["
    for index in range(num_bytes - 1, -1, -1):
        address_string += string.hexdigits[0xF & (MAC_address >> (index * 8 + 4))]
        address_string += string.hexdigits[0xF & (MAC_address >> (index * 8))]
        if index:
            address_string += ":"
        else:
            address_string += "]!"
    return address_string
        
def address_string_to_MAC(address_string):
    "Convert an address string to a MAC address"
    if address_string[0] == "[":
        return int("0x" + string.replace(address_string[1:-2], ":", ""), 16)
    else:
        return int("0x" + string.replace(address_string[0:-1], ":", ""), 16)
        
def short_to_address_string(short_address):
    "Convert a short (network) address to a string"
    return "[%02X%02X]!" % ((short_address >> 8) & 0xFF, short_address & 0xFF)    
    
def address_string_to_short(address_string):
    "Convert an address string to a short (network) address"
    return int("0x" + address_string[1:-2], 16)


class API_Data:
    """Base class for storing data in an API message
    Also stores a static frame ID for different messages to use."""

    xbee_frame_id = 1
    "Frame ID for transmitting to the XBee node"
    rx_id = 0
    "Receive API message type ID"
    tx_id = 0
    "Transmit API message type ID"

    def __init__(self):
        "Creates API_Data object"
        self.data = ""
        self.frame_id = 0

    @staticmethod
    def next_frame():
        "Returns the next frame ID for sending a message"
        API_Data.xbee_frame_id += 1
        if API_Data.xbee_frame_id >= 256:
            API_Data.xbee_frame_id = 1
        return API_Data.xbee_frame_id
    
    def extract(self, cmd_data):
        "Base class just grabs the whole buffer"
        self.data = cmd_data
        
    def export(self):
        "Returns the whole buffer as a string"
        return self.data


class IEEE_802_15_4_64_Data(API_Data):
    "Extracts an 802.15.4 frame from the XBee Rx message and outputs a XBee transmit frame."
    BROADCAST_RADIUS = 0
    "Number of hops on the XBee network."
    rx_id = 0x80
    "Receive API message type ID"
    tx_id = 0x00
    "Transmit API message type ID"
    
    def __init__(self, source_address = None, destination_address = None, payload = ""):
        "Initializes the zb_data with no data."
        API_Data.__init__(self)        
        self.source_address = source_address
        self.destination_address = destination_address
        self.payload = payload
        self.rssi = 0

    def extract(self, cmd_data):
        "Extract a XBee message from a 0x80 XBee frame cmd_data"
        if len(cmd_data) < 10:
            #Message too small, return error
            logger.warn("Malformed message - too small")
            return -1
        source_address_64, self.rssi, options = struct.unpack(">QBB", cmd_data[:10])
        self.payload = cmd_data[10:]
        # use the device's EUI address
        address_string = MAC_to_address_string(source_address_64)            
        # convert source address to proper string format, create address tuple
        # NOTE: 6th parameter is only used for TX Status - always set to zero.
        self.source_address = (address_string, 0, 0, 0, options, 0)
        self.destination_address = ("", 0, 0, 0)
        return 0
        
    def export(self):
        "Export a XBee message as a 0x00 XBee frame cmd_data"
        self.frame_id = self.next_frame()
        cmd_data = chr(self.frame_id) #frame id
        cmd_data += struct.pack(">Q", address_string_to_MAC(self.destination_address[0])) # destination_address_64
        if len(self.destination_address) > 4:
            cmd_data += chr(self.destination_address[4])
        else:
            cmd_data += chr(0) # default to no options
        cmd_data += self.payload
        return cmd_data


class IEEE_802_15_4_16_Data(API_Data):
    "Extracts an 802.15.4 frame from the XBee Rx message and outputs a XBee transmit frame."
    BROADCAST_RADIUS = 0
    "Number of hops on the XBee network."
    rx_id = 0x81
    "Receive API message type ID"
    tx_id = 0x01
    "Transmit API message type ID"
    
    def __init__(self, source_address = None, destination_address = None, payload = ""):
        "Initializes the zb_data with no data."
        API_Data.__init__(self)        
        self.source_address = source_address
        self.destination_address = destination_address
        self.payload = payload
        self.rssi = 0

    def extract(self, cmd_data):
        "Extract a XBee message from a 0x81 XBee frame cmd_data"
        if len(cmd_data) < 4:
            #Message too small, return error
            logger.warn("Malformed message - too small")
            return -1
        source_address_16, self.rssi, options = struct.unpack(">HBB", cmd_data[:4])
        self.payload = cmd_data[4:]
        # use the device's short address
        address_string = short_to_address_string(source_address_16)            
        # convert source address to proper string format, create address tuple
        # NOTE: 6th parameter is only used for TX Status - always set to zero.
        self.source_address = (address_string, 0, 0, 0, options, 0)
        self.destination_address = ("", 0, 0, 0)
        return 0
        
    def export(self):
        "Export a XBee message as a 0x01 XBee frame cmd_data"
        self.frame_id = self.next_frame()
        cmd_data = chr(self.frame_id) #frame id
        cmd_data += struct.pack(">H", address_string_to_short(self.destination_address[0])) # destination_address_16
        if len(self.destination_address) > 4:
            cmd_data += chr(self.destination_address[4])
        else:
            cmd_data += chr(0) # default to no options
        cmd_data += self.payload
        return cmd_data


class ZB_Data(API_Data):
    "Extracts a ZigBee frame from the XBee Rx message and outputs a XBee transmit frame."
    BROADCAST_RADIUS = 0
    "Number of hops on the XBee network."
    rx_id = 0x91
    "Receive API message type ID"
    tx_id = 0x11
    "Transmit API message type ID"
    
    def __init__(self, source_address = None, destination_address = None, payload = ""):
        "Initializes the zb_data with no data."
        API_Data.__init__(self)        
        self.source_address = source_address
        self.destination_address = destination_address
        self.payload = payload

    def extract(self, cmd_data):
        "Extract a XBee message from a 0x91 XBee frame cmd_data"
        if len(cmd_data) < 17:
            #Message too small, return error
            logger.warn("Malformed message - too small")
            return -1
        source_address_64, source_address_16, source_endpoint, destination_endpoint, \
            cluster_id, profile_id, options = struct.unpack(">QHBBHHB", cmd_data[:17])
        self.payload = cmd_data[17:]
        if source_address_64 == 0xFFFFFFFFFFFFFFFF:
            # only short address information available
            address_string = short_to_address_string(source_address_16)
            #print "Using short address: ", address_string
        else:
            # use the device's EUI address
            address_string = MAC_to_address_string(source_address_64)            
        # convert source address to proper string format, create address tuple
        # NOTE: 6th parameter is only used for TX Status - always set to zero.
        self.source_address = (address_string, source_endpoint, profile_id, cluster_id, options, 0)
        self.destination_address = ("", destination_endpoint, profile_id, cluster_id)
        return 0
        
    def export(self):
        "Export a XBee message as a 0x11 XBee frame cmd_data"
        self.frame_id = self.next_frame()
        cmd_data = chr(self.frame_id) #frame id
        if len(self.destination_address[0]) == 7: # [XXXX]! short address
            cmd_data += struct.pack(">Q", 0xFFFFFFFFFFFFFFFF)
            cmd_data += struct.pack(">H", address_string_to_short(self.destination_address[0]))
        else: # long address
            cmd_data += struct.pack(">Q", address_string_to_MAC(self.destination_address[0])) # destination_address_64
            # TTDO: should set to last know short address to improve performance
            cmd_data += chr(0xFF) + chr(0xFE) # destination_address_16
        cmd_data += struct.pack(">BBHHB", self.source_address[1], # source_endpoint
                                          self.destination_address[1],# destination_endpoint
                                          self.destination_address[3], # cluster_id
                                          self.destination_address[2], # profile_id
                                          self.BROADCAST_RADIUS) # broadcast radius
        if len(self.destination_address) > 4:
            cmd_data += chr(self.destination_address[4])
        else:
            cmd_data += chr(0) # default to no options
        cmd_data += self.payload
        return cmd_data
    

class Local_AT_Data(API_Data):
    "Extracts from an AT Response frame and exports to an AT Command frame."
    rx_id = 0x88
    "Receive API message type ID"
    tx_id = 0x08
    "Transmit API message type ID"
    def __init__(self, AT_cmd = "", value = ""):
        API_Data.__init__(self)
        "Initializes the AT frame with no data."
        self.AT_cmd = AT_cmd
        "Two character string of the character command"
        self.status = 0
        "Status of a received message"
        self.value = value
        "Value received or to be set for the AT command"

    def extract(self, cmd_data):
        "Extract an AT response message from a 0x88 xbee frame cmd_data"
        if len(cmd_data) < 4:
            #Message too small, return error
            return -1
        self.frame_id = ord(cmd_data[0])
        self.AT_cmd = cmd_data[1:3]
        self.status = ord(cmd_data[3])
        self.value = cmd_data[4:] #NOTE: some messages have no value
        return 0
        
    def export(self):
        "Export an AT message as a 0x08 xbee frame cmd_data"
        self.frame_id = self.next_frame()
        cmd_data = chr(self.frame_id)
        cmd_data += self.AT_cmd
        cmd_data += self.value
        return cmd_data


class Remote_AT_Data(API_Data):
    "Extracts from a Remote AT Response frame and exports to a Remote AT Command frame."
    rx_id = 0x97
    "Receive API message type ID"
    tx_id = 0x17
    "Transmit API message type ID"
    def __init__(self, remote_address = None, AT_cmd = "", value = ""):
        API_Data.__init__(self)
        "Initializes the AT frame with no data."
        self.remote_address = remote_address
        "Extended address of XBee that is having AT parameter set, stored as formatted string."
        self.AT_cmd = AT_cmd
        "Two character string of the character command"
        self.status = 0
        "Status of a received message"
        self.value = value
        "Value received or to be set for the AT command"

    def extract(self, cmd_data):
        "Extract a remote AT response message from a 0x97 xbee frame cmd_data"
        if len(cmd_data) < 14: #TODO: make sure this is the right number.
            #Message too small, return error
            return -1
        self.frame_id, source_address_64, source_address_16 = struct.unpack(">BQH", cmd_data[:11])
        self.remote_address = MAC_to_address_string(source_address_64)
        self.AT_cmd = cmd_data[11:13]
        self.status = ord(cmd_data[13])
        self.value = cmd_data[14:] #NOTE: some messages have no value
        return 0
        
    def export(self):
        "Export a remote AT message as a 0x17 xbee frame cmd_data"
        self.frame_id = self.next_frame()
        cmd_data = chr(self.frame_id)
        cmd_data += struct.pack(">Q", address_string_to_MAC(self.remote_address)) # destination_address_64
        cmd_data += chr(0xFF) + chr(0xFE) # destination_address_16
        cmd_data += chr(0x02) # Command Options (Always set immediately)        
        cmd_data += self.AT_cmd
        cmd_data += self.value
        return cmd_data


class Register_Device_Data(API_Data):
    "Extracts from a Register Joining Device Status frame and exports to a Register Device frame."
    rx_id = 0xA4
    "Receive Register Joining Device Status message type ID"
    tx_id = 0x24
    "Register Device message type ID"
    # status values
    SUCCESS = 0x00
    INVALID_ADDRESS = 0xB3
    KEY_NOT_FOUND = 0xFF
    def __init__(self, remote_address = None, link_key = ""):
        API_Data.__init__(self)
        "Initializes the register device with no data."
        self.remote_address = remote_address
        "Extended address of device that is being added to the network, stored as formatted string."
        self.link_key = link_key
        "Big-endian binary string containing link key (up to 16 bytes)"
        self.status = 0
        "Status of device registration"

    def extract(self, cmd_data):
        "Extract a register device response message from a 0xA4 xbee frame cmd_data"
        if len(cmd_data) < 2:
            #Message too small, return error
            return -1
        self.frame_id = ord(cmd_data[0])
        self.status = ord(cmd_data[1])
        return 0
        
    def export(self):
        "Export a register device message as a 0x24 xbee frame cmd_data"
        self.frame_id = self.next_frame()
        cmd_data = chr(self.frame_id)
        cmd_data += struct.pack(">Q", address_string_to_MAC(self.remote_address)) # destination_address_64
        cmd_data += chr(0xFF) + chr(0xFE) # destination_address_16, always set to 0xFFFE
        cmd_data += chr(0x00) # Key Options (Always set to 0)        
        cmd_data += self.link_key
        return cmd_data


class IEEE_802_15_4_Tx_Status_Data(API_Data):
    "Extracts from an 802.15.4 Tx Status frame."
    rx_id = 0x89
    "Receive ZigBee Tx Status message type ID"
    # Delivery Status
    SUCCESS = 0x00
    NO_ACK_RECEIVED = 0x01
    CCA_FAILURE = 0x02
    PURGED = 0x03

    def __init__(self, delivery_status = SUCCESS):
        API_Data.__init__(self)
        "Initializes the register device with no data."
        self.delivery_status = delivery_status
        "If the message was delivered or if there was an error"

    def extract(self, cmd_data):
        "Extract a ZigBee Tx Status message from a 0x8B xbee frame cmd_data"
        if len(cmd_data) < 2:
            #Message too small, return error
            return -1
        # extract data
        self.frame_id, self.delivery_status = struct.unpack(">BB", cmd_data[:2])
        return 2
        
    def export(self):
        "Will export a TX Status Message.  May be used for local message routing."
        cmd_data = chr(self.frame_id)
        cmd_data += chr(self.delivery_status)
        return cmd_data


class ZigBee_Tx_Status_Data(API_Data):
    "Extracts from a ZigBee Tx Status frame."
    rx_id = 0x8B
    "Receive ZigBee Tx Status message type ID"
    # Delivery Status
    SUCCESS = 0x00
    CCA_FAILURE = 0x02
    NETWORK_ACK_FAILURE = 0x21
    NOT_JOINED_TO_NETWORK = 0x22
    SELF_ADDRESSED = 0x23
    ADDRESS_NOT_FOUND = 0x24
    NO_ROUTE_FOUND = 0x25
    INVALID_BINDING_TABLE_INDEX = 0x2B
    INVALID_ENDPOINT = 0x2C
    DATA_PAYLOAD_TOO_BIG = 0x74
    KEY_NOT_AUTHORIZED = 0xBB
    # Discovery Status
    NO_DISCOVERY_OVERHEAD = 0x00
    ADDRESS_DISCOVERY = 0x01
    ROUTE_DISCOVERY = 0x02
    ADDRESS_AND_ROUTE_DISCOVERY = 0x03

    def __init__(self, remote_network_address = "[FFFE]!", transmit_retry_count = 0, delivery_status = SUCCESS, discovery_status = NO_DISCOVERY_OVERHEAD):
        API_Data.__init__(self)
        "Initializes the register device with no data."
        self.remote_network_address = remote_network_address
        "Short address of device that is ACKing the message we sent."
        self.transmit_retry_count = transmit_retry_count
        "How many transmission attempts the Xbee made"
        self.delivery_status = delivery_status
        "If the message was delivered or if there was an error"
        self.discovery_status = discovery_status
        "If there was any address or route discovery overhead"

    def extract(self, cmd_data):
        "Extract a ZigBee Tx Status message from a 0x8B xbee frame cmd_data"
        if len(cmd_data) < 6:
            #Message too small, return error
            return -1
        # extract data
        self.frame_id, short_address, self.transmit_retry_count, self.delivery_status, self.discovery_status = struct.unpack(">BHBBB", cmd_data)
        #convert short network address to string
        self.remote_network_address = short_to_address_string(short_address)
        return 6
        
    def export(self):
        "Will export a TX Status Message.  May be used for local message routing."
        cmd_data = chr(self.frame_id)
        cmd_data += struct.pack(">H", address_string_to_short(self.remote_network_address)) # remote_address_16
        cmd_data += chr(self.transmit_retry_count)        
        cmd_data += chr(self.delivery_status)
        cmd_data += chr(self.discovery_status)
        return cmd_data            


class IEEE_802_15_4_64_IO(API_Data):
    "Extracts from an 802.15.4 Receive 64-bit Address IO."
    rx_id = 0x82

    def __init__(self, source_address = None, destination_address = None, rssi=None, payload = ""):
        "Initializes the IO data with no data."
        API_Data.__init__(self)        
        self.source_address = source_address
        self.rssi = rssi
        self.payload = payload

    def extract(self, cmd_data):
        "Extract a XBee message from a 0x82 XBee frame cmd_data"
        if len(cmd_data) < 10:
            #Message too small, return error
            logger.warn("Malformed message - too small")
            return -1
        source_address_64, self.rssi, options = struct.unpack(">QBB", cmd_data[:10])
        self.payload = cmd_data[10:]
        # use the device's EUI address
        address_string = MAC_to_address_string(source_address_64)            
        # convert source address to proper string format, create address tuple
        # NOTE: 6th parameter is only used for TX Status - always set to zero.
        self.source_address = (address_string, 0xe8, 0x0, 0x92, options, 0) #NOTE: 0xe8 is quirk of socket
        return 0

class IEEE_802_15_4_16_IO(API_Data):
    "Extracts from an 802.15.4 Receive 16-bit Address IO."
    rx_id = 0x83

    def __init__(self, source_address = None, destination_address = None, rssi=None, payload = ""):
        "Initializes the IO data with no data."
        API_Data.__init__(self)        
        self.source_address = source_address
        self.rssi = rssi
        self.payload = payload

    def extract(self, cmd_data):
        "Extract a XBee message from a 0x83 XBee frame cmd_data"
        if len(cmd_data) < 4:
            #Message too small, return error
            logger.warn("Malformed message - too small")
            return -1
        source_address_16, self.rssi, options = struct.unpack(">HBB", cmd_data[:4])
        self.payload = cmd_data[4:]
        # use the device's EUI address
        address_string = short_to_address_string(source_address_16)            
        # convert source address to proper string format, create address tuple
        # NOTE: 6th parameter is only used for TX Status - always set to zero.
        self.source_address = (address_string, 0xe8, 0x0, 0x93, options, 0) #NOTE: 0xe8 is quirk of socket
        return 0


class API_Message:
    "Creates API message for the XBee"
    
    API_IDs = {ZB_Data.rx_id: ZB_Data, 
               Local_AT_Data.rx_id: Local_AT_Data, 
               Remote_AT_Data.rx_id: Remote_AT_Data,\
               Register_Device_Data.rx_id: Register_Device_Data, 
               ZigBee_Tx_Status_Data.rx_id: ZigBee_Tx_Status_Data, 
               IEEE_802_15_4_Tx_Status_Data.rx_id: IEEE_802_15_4_Tx_Status_Data,
               IEEE_802_15_4_64_Data.rx_id: IEEE_802_15_4_64_Data, 
               IEEE_802_15_4_16_Data.rx_id: IEEE_802_15_4_16_Data,
               IEEE_802_15_4_64_IO.rx_id: IEEE_802_15_4_64_IO,
               IEEE_802_15_4_16_IO.rx_id: IEEE_802_15_4_16_IO}
    "Stores the different APIs"
    
    def __init__(self):
        self.length = 0
        "Length field of the frame"
        self.API_ID = 0
        "Frame message ID."
        self.cmd_data = ""
        "Data payload for the frame"
        self.api_data = API_Data()
        "Formatted command data"
        self.checksum = 0
        "Checksum value for the message"
        
    def __len__(self):
        "Length of the entire message"
        return self.length + 4

    def calc_checksum(self):
        "Calculates the checksum, based on cmd_data"
        checksum = self.API_ID
        for byte in self.cmd_data:
            checksum += ord(byte)
            checksum &= 0xFF
        return 0xFF - checksum
    
    def set_length(self):
        "Calculates the length and sets it, based on cmd_data"
        self.length = len(self.cmd_data) + 1

    def set_API_ID(self):
        "Sets the API_ID from the message data type"
        if self.api_data.tx_id:
            self.API_ID = self.api_data.tx_id 
    
    def is_valid(self):
        "Verifies that the checksum is correct"
        return self.checksum == self.calc_checksum()
        
    def extract(self, buffer):
        """Extracts the message from a string
        returns number of bytes used on success
        -1 when the buffer is not big enough(string not long enough)"""
        if len(buffer) < 5:
            return -1
        
        # pull out length (MSB)
        length = ord(buffer[1]) * 255 + ord(buffer[2])
        
        if len(buffer) < length + 4:
            return -1

        # we have a full XBee message, lets extract it.
        self.length = length
        self.API_ID = ord(buffer[3])
        self.cmd_data = buffer[4:length+3]
        if self.API_ID in self.API_IDs.keys():
            self.api_data = self.API_IDs[self.API_ID]()
        else:
            self.api_data = API_Data()
        self.api_data.extract(self.cmd_data)
        self.checksum = ord(buffer[length + 3])

        return len(self)

        
    def export(self, recalculate_checksum = 1):
        """Exports the message to a string, will recalculate checksum by default.
        Will also re-calculate the length field and lookup API_ID from message type."""
        self.set_API_ID() # must be done before calculating checksum
        self.cmd_data = self.api_data.export() # must be done before calculating checksum
        self.checksum = self.calc_checksum() # calculate the new checksum and set it
        self.set_length() # set the new length
        return chr(0x7E) + chr(self.length / 255) + chr(self.length & 0xFF) + chr(self.API_ID) + self.cmd_data + chr(self.checksum)


class ZDO_Frame:
    def __init__(self, buf = None, address = None):
        """Parse frame and store the address, create blank frame if no buffer."""
        self.address = address
        if buf is None:
            self.transaction_sequence_number = 0
            self.payload = ""
        else:
            self.transaction_sequence_number = ord(buf[0])
            self.payload = buf[1:]
    
    def export(self):
        """Create frame as a string of bytes"""
        return chr(self.transaction_sequence_number) + self.payload
   

class Conversation:
    """Base class for managing command/response pairs by matching frame IDs."""
    default_timeout = 40
    """Default timeout period for waiting for response for conversation"""
    
    def __init__(self, frame, callback = None, timeout_callback = None, timeout = None, extra_data = None):
        self.start_time = time.time()
        self.active = True  #will switch to false once this conversation has finished
        self.frame = frame
        #The address attribute is primarily used in error reporting.
        #Some conversations may not have a valid frame but will override self.address appropriately.
        if frame is not None:
            self.address = frame.address
        else:
            self.address = None
        self.callback = callback
        self.timeout_callback = timeout_callback
        if timeout is None:
            self.timeout = self.default_timeout
        else:
            self.timeout = timeout
        self.extra_data = extra_data  #there are times when it is useful to store additional information in a conversation
        
    def match_frame(self, frame):
        #a base conversation object should always fail matches
        return False
        
    def tick_sec(self):
        if (time.time() - self.start_time > self.timeout):
            # we timed out on the response
            self.active = False
            if self.timeout_callback is not None:
                self.timeout_callback(self)
            else:
                #TTDO: this is now an uncommon case; should we just print an error or still rely
                #on a raise (and catch in tick_sec)?
                #raise Exception("Conversation Timeout: Address = %s" % str(self.frame.address))
                pass


class ZDO_Conversation(Conversation):
    def match_frame(self, frame):
        matched = False
        if (self.frame.address[0] == frame.address[0] and
            self.frame.transaction_sequence_number == frame.transaction_sequence_number):
            matched = True
            self.active = False #terminate one-shot conversation if a match occurs 
        return matched


class ZDO_Device_annce_cluster_server:
    cluster_id = 0x0013
    #command format:
    #2 - NWK address
    #8 - IEEE address
    #1 - Device capability bitmap
    #Note that device announce is broadcast to other devices and does not expect a response.
    #The device announce is sent automatically when the device joins the network, so no
    #send_command method is needed.
    def __init__(self, callback = None):
        self.callback = callback
        "A callback to be called when a device announce message comes in"
    
    def register_callback(self, callback): 
        "Set the callback to be called when a device announce message comes in" 
        self.callback = callback
          
    def handle_message(self, frame):
        if self.callback is not None:
            try:
                record = Device_Annce()
                record.extract(frame.payload)
                # TTDO: should this be a record list?
                self.callback(record)
            except Exception, e:
                logger.debug("Error: ZDO_Device_annce_cluster_server: %s" % str(e))


class ZDO_Mgmt_Lqi_cluster_client:
    cluster_id = 0x0031
    
    def __init__(self, xbee = None):
        self.conversations = []
        self.xbee = xbee
        self.sequence_number = 0
    
    def send_frame(self, frame):
        self.xbee.send_zb(0, frame.address, frame.export())
    
    def send_command(self, dest_address, start_index, callback = None):
        if callback == None:
            callback = self.default_callback
        frame = ZDO_Frame()
        frame.transaction_sequence_number = self.next_sequence_number()
        frame.payload = chr(start_index)
        frame.address = (dest_address, 0, 0, self.cluster_id)
        self.send_frame(frame)
        self.conversations.append(ZDO_Conversation(frame, callback))
                                  
    def next_sequence_number(self):
        "Get the next transaction sequence number to use for sending a message."
        self.sequence_number += 1
        self.sequence_number &= 0xFF # limit from 0-255 (8-bit value)
        return self.sequence_number
    
    def handle_message(self, frame):
        #print "Received LQI message from %s" % str(source_address)
        #purge any dead conversations
        for temp_conversation in self.conversations[:]:
            if temp_conversation.active == False:
                self.conversations.remove(temp_conversation)
        #check all conversations for matches with the frame; if no conversations match raise exception 
        conversation = None
        for temp_conversation in self.conversations:
            if temp_conversation.match_frame(frame):
                conversation = temp_conversation
                break
        
        if conversation is not None:
            if conversation.callback is not None:
                #print [hex(ord(x)) for x in frame.payload]
                mgmt_lqi_rsp = Mgmt_Lqi_rsp()
                mgmt_lqi_rsp.extract(frame.payload)
                conversation.callback(conversation, frame, mgmt_lqi_rsp)
                return True
        else:   #no conversation matched, raise exception
            #raise Exception("ZDO_Mgmt_Lqi_cluster_client: Received an unexpected message from %s" % str(source_address))
            return False
        
    def default_callback(self, conversation, frame, record_list):
        pass


class LQI_aggregator:
    def __init__(self, client_lqi_cluster, dest_address, start_index = 0, callback = None):
        self.client_lqi_cluster = client_lqi_cluster
        self.dest_address = dest_address
        self.start_index = start_index
        self.neighbor_table_descriptors = []
        self.final_callback = callback
        self.client_lqi_cluster.send_command(self.dest_address, start_index, self.callback)
    
    def callback(self, conversation, frame, lqi_record):
        #print "Internal LQI_aggregator callback"
        self.neighbor_table_descriptors.extend(lqi_record.neighbor_table_list)
        end_index = lqi_record.start_index + len(lqi_record.neighbor_table_list)
        if end_index < lqi_record.neighbor_table_entries:
            #send another command            
            self.client_lqi_cluster.send_command(self.dest_address, end_index)
        else:
            self.final_callback(self.neighbor_table_descriptors)
    
    def default_callback(self, conversation, frame, record_list):
        pass


class NeighborTableDescriptorRecord:
    def __init__(self,
                 pan_extended = None,
                 addr_extended = None,
                 addr_short = None,
                 device_type = None,
                 rx_on_when_idle = None,
                 relationship = None,
                 permit_joining = None,
                 depth = None,
                 lqi = None):
        
        self.pan_extended = pan_extended
        self.addr_extended = addr_extended
        self.addr_short = addr_short
        self.device_type = device_type
        self.rx_on_when_idle = rx_on_when_idle
        self.relationship = relationship
        self.permit_joining = permit_joining
        self.depth = depth
        self.lqi = lqi
    
    def extract(self, buf):
        try:
            self.pan_extended,\
            self.addr_extended,\
            self.addr_short,\
            byte1,\
            byte2,\
            self.depth,\
            self.lqi = struct.unpack("<QQHBBBB", buf[:22])
            
            self.device_type = byte1 & 0x03
            self.rx_on_when_idle = (byte1 & 0x0C) >> 2
            self.relationship = (byte1 & 0x70) >> 4
            self.permit_joining = (byte2 & 0x03)          
            
            self.addr_extended = MAC_to_address_string(self.addr_extended, 8)
            self.addr_short = short_to_address_string(self.addr_short)
            return 22
        except Exception, e:
            raise Exception("Error: NeighborTableListRecord.extract() - %s" % e)
    
    def export(self):
        byte1 = self.device_type | (self.rx_on_when_idle << 2) | (self.relationship << 4)
        
        buf = struct.pack("<QQHBBBB",\
                          self.pan_extended,\
                          self.addr_extended,\
                          self.addr_short,\
                          byte1,\
                          self.permit_joining,\
                          self.depth,\
                          self.lqi)
        
        return buf


class Mgmt_Lqi_rsp:
    def __init__(self,
                 status = None,
                 neighbor_table_entries = None,
                 start_index = None,
                 neighbor_table_list = None):
        
        if neighbor_table_list is None:
            neighbor_table_list = []
        
        self.status = status
        self.neighbor_table_entries = neighbor_table_entries
        self.start_index = start_index
        self.neighbor_table_list = neighbor_table_list
    
    def extract(self, buffer):
        self.status = ord(buffer[0])
        if self.status == 0: #SUCCESS 
            self.neighbor_table_entries, self.start_index, neighbor_table_list_count = struct.unpack("<BBB", buffer[1:4])
            if neighbor_table_list_count > 0:
                offset = 4
                for i in xrange(neighbor_table_list_count):
                    record = NeighborTableDescriptorRecord()
                    offset += record.extract(buffer[offset:])
                    self.neighbor_table_list.append(record)
    
    def export(self):
        buffer = struct.pack("<BBBB",\
                             self.status,\
                             self.neighbor_table_entries,\
                             self.start_index,\
                             len(self.neighbor_table_list))
                             
        for neighbor_table_entry in self.neighbor_table_list:
            buffer += neighbor_table_entry.export()
        return buffer


class Device_Annce:
    def __init__(self,
                 nwk_addr = None,
                 IEEE_addr = None,
                 capability = None):
        self.nwk_addr = nwk_addr
        self.IEEE_addr = IEEE_addr
        self.capability = capability
    
    def extract(self, buffer):
        #message format:
        #2 - NWK address of this device
        #8 - IEEE address of this device
        #1 - Capability of the local device 
        #Capability Format:
        #Field Name                     Length (Bits)
        #Alternate PAN coordinator        1
        #Device type                      1
        #Power source                     1
        #Receiver on when idle            1
        #Reserved                         2
        #Security capability              1
        #Allocate address                 1         
        try:
            self.nwk_addr, self.IEEE_addr, self.capability = struct.unpack("<HQB", buffer[0:11])
        except Exception,e:
            raise Exception("Error: Device_Annce.extract() - %s" % e)


class XBee:
    "Handles the connection to an XBee module"
    DIGI_PROFILE_ID = 0xC105
    DIGI_MANUFACTURER_ID = 0x101E
    device_types = ["coordinator", "router", "end"]
    
    def __init__(self, serial = None):
        # mutual exclusion lock:
        global _global_lock
        _global_lock = RLock()
        "Creates the connection to the XBee using the serial port."
        self.serial = serial
        "Serial port that connects to the xbee"
        self.rx_messages = {}
        "Messages received from the XBee. Key = endpoint_id, value = (payload, full_source_address)"
        self.rx_buffer = ""
        "Receive buffer for the serial port"
        self.node_list = []
        "Node list for the get_node_list function"
        self.tx_status = {}
        "Tx Status message buffer, key = XBee frame ID, value = (transaction_id, endpoint_id)"
        # This needs to be here to allow us to support broadcasts at the top of ZigBee_Node.tick()
        self.rx_messages[0xFF] = []
        
        self.lqi_cluster = ZDO_Mgmt_Lqi_cluster_client(self)
        self.device_annce_cluster = ZDO_Device_annce_cluster_server(self.device_announce_handler)
        self.hw_version = None
        self.sw_version = None

    def close_serial(self):
        global com_port_opened
        try:
            _global_lock.acquire(True) # make sure other operations aren't happening
            if self.serial:
                self.serial.close()
            self.serial = None
            self.rx_buffer = ""
            self.node_list = []
            #NOTE: leaving any messages that had been completely received
            com_port_opened = False  
        finally:
            _global_lock.release()

    def set_version(self):
        self.hw_version = struct.unpack(">H", self.ddo_get_param(None, "HV", force_com=True))[0]
        self.sw_version = struct.unpack(">H", self.ddo_get_param(None, "VR", force_com=True))[0]
    
    def is_series_1(self):
        return (self.hw_version & 0xFF00) in (0x1700,)
    
    def is_802_15_4(self):
        return self.is_series_1() and ((self.sw_version & 0xF000) == 0x1000)
    
    def register_endpoint(self, endpoint_id):
        "Registers an endpoint to save messages for"
        if endpoint_id not in self.rx_messages:
            self.rx_messages[endpoint_id] = []

    def unregister_endpoint(self, endpoint_id):
        "Un-registers an endpoint, so that the messages are no long saved"
        if endpoint_id in self.rx_messages:
            del self.rx_messages[endpoint_id]

    def recv(self, endpoint_id):
        "Reads the messages from the XBee.  Returns from address and payload as a string"
        _global_lock.acquire(True)
        try:
            if self.serial is None or not self.serial.isOpen():
                return None, None
                #TODO: raise exception?
            # checks for any new messages
            self.read_messages()
            # check to see if there are any messages waiting
            if len(self.rx_messages[endpoint_id]):
                # there was a message
                recv_tuple = self.rx_messages[endpoint_id].pop(0)
                return recv_tuple[0], recv_tuple[1] #payload, address
        finally:
            _global_lock.release()
        return None, None

    def send(self, message):
        "Send an API message"
        _global_lock.acquire(True)
        try:
            # dev_idea: could keep track of frame_id and the responses.
            if self.serial is not None and self.serial.isOpen():
                self.serial.write(message.export())
                debug_str = ""
                if message.API_ID == 0x11:  #TODO: temporary filter
                    debug_str = "TX: API ID = %s\n" % hex(message.API_ID)
                    #frame ID
                    debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[0:1]]) + "]:"
                    #64-bit address        
                    debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[1:9]]) + "]:"
                    #16-bit address        
                    debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[9:11]]) + "]:"
                    #source endpoint      
                    debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[11:12]]) + "]:"
                    #destination endpoint      
                    debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[12:13]]) + "]:"
                    #cluster     
                    debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[13:15]]) + "]:"
                    #profile     
                    debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[15:17]]) + "]:"
                    #broadcast radius   
                    debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[17:18]]) + "]:"
                    #options   
                    debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[18:19]]) + "]:"
                    #payload     
                    debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[19:]]) + "]"
                    if MESH_TRACEBACK and debug_callback is not None:
                        debug_callback(debug_str)
                else:
                    debug_str = "TX: API ID = %s\n" % hex(message.API_ID)
                    debug_str += str([hex(ord(x)) for x in message.cmd_data])    
                logger.debug(debug_str)
        finally:
            _global_lock.release()
        
    def send_zb(self, source_endpoint, destination_address, payload):
        "Sends message to the XBee."
        if destination_address[0] == "":
            # this is a local message, loop back to received messages
            # mask out profile and cluster ID
            local_endpoint = destination_address[1]
            if local_endpoint in self.rx_messages:
                tx_status_tuple = None
                if len(destination_address) >= 6 and destination_address[5] != -1:
                    # create the tx status response
                    tx_status_tuple = (0, "00:00:00:00:00:00:00:00!", source_endpoint, 0xC105, 0x8B, 0, destination_address[5])
                
                # create the tuple to store the message
                # the source address will not have the profile and cluster IDs
                # these are added based on the destination address
                options = 0
                if len(destination_address) > 4:
                    # flag APS encryption if in original options
                    options = destination_address[4] & socket.XBS_OPT_TX_APSSEC 
                    # flag packet acknowledged, if not disabled
                    options |= destination_address[4] ^ socket.XBS_OPT_RX_ACK 
                full_source_address = ("", source_endpoint, destination_address[2], destination_address[3], options)
                recv_tuple = (payload, full_source_address)
                # add data to the message queue
                if tx_status_tuple is not None:
                    self.rx_messages[source_endpoint].append(tx_status_tuple)                            
                self.rx_messages[local_endpoint].append(recv_tuple)

        else:
            # send message out the XBee
            message = API_Message()
            if self.is_802_15_4():
                # create an 802.15.4 message
                if len(destination_address[0]) <= 8: #'[xxxx]!' or '[xx:xx]!'
                    # this is a 16-bit address
                    message.API_ID = IEEE_802_15_4_16_Data.tx_id
                    zb_data = IEEE_802_15_4_16_Data()
                else:
                    # this is a 64-bit address 
                    message.API_ID = IEEE_802_15_4_64_Data.tx_id
                    zb_data = IEEE_802_15_4_64_Data()
            else:
                #assume this radio uses the ZB packets
                message.API_ID = ZB_Data.tx_id
                zb_data = ZB_Data()
            zb_data.source_address = ("", source_endpoint, 0, 0)
            zb_data.destination_address = destination_address
            zb_data.payload = payload
            message.api_data = zb_data
            self.send(message)
        
            #Handle 6th address parameter to receive transmit status.
            if len(destination_address) >= 6 and destination_address[5] != -1:
                # track Tx Status message
                transaction_id = destination_address[5]
                frame_id = message.api_data.frame_id 
                self.tx_status[frame_id] = (transaction_id, source_endpoint)

    def process_message(self, message, message_buffer, AT_frame_id = 0, force_com=False):
        # pass data to XBS_PROT_XAPI sockets if applicable
        if -0xFF in self.rx_messages:
            # add to the generic message socket
            self.rx_messages[-0xFF].append((message_buffer, ('[0000]!', 0, 0, 0, 0, 0)))
        if -message.API_ID in self.rx_messages: #NOTE: API_ID = 0 is never received from XBee.
            # add to the message specific socket
            self.rx_messages[-message.API_ID].append((message_buffer, ('[0000]!', 0, 0, 0, 0, 0)))

        debug_str = ""                        
        if message.API_ID == 0x91:  #TTDO: temporary filter
            debug_str = "RX: API ID = %s\n" % hex(message.API_ID)
            #64-bit address        
            debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[0:8]]) + "]:"
            #16-bit address
            debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[8:10]]) + "]:"
            #source endpoint
            debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[10:11]]) + "]:"
            #destination endpoint
            debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[11:12]]) + "]:"
            #cluster ID
            debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[12:14]]) + "]:"
            #profile ID
            debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[14:16]]) + "]:"
            #options
            debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[16:17]]) + "]:"
            #payload
            debug_str += "[" + ", ".join(["%02X" %(ord(x)) for x in message.cmd_data[17:]]) + "]"
            if MESH_TRACEBACK and debug_callback is not None:
                debug_callback(debug_str)
        else:
            debug_str = "RX: API ID = %s\n" % hex(message.API_ID)
            debug_str += str([hex(ord(x)) for x in message.cmd_data])
        logger.debug(debug_str)
        
        if message.API_ID == ZB_Data.rx_id: # CMD ID for explicit receive
            #extract the zb_data
            zb_data = message.api_data
            # make sure the address is registered, check with address = ""
            local_endpoint = zb_data.destination_address[1]
            
            # check for Device Announce
            if zb_data.destination_address[1] == 0 and\
                zb_data.destination_address[2] == 0 and\
                zb_data.destination_address[3] == 0x0013:
                #print "ZDO Announce Message Received"
                frame = ZDO_Frame(zb_data.payload, zb_data.source_address)                           
                self.device_annce_cluster.handle_message(frame)                        
            # check for LQI request
            elif zb_data.destination_address[1] == 0 and\
                zb_data.destination_address[2] == 0 and\
                zb_data.destination_address[3] == 0x8031:
                frame = ZDO_Frame(zb_data.payload, zb_data.source_address)                           
                self.lqi_cluster.handle_message(frame)
            
            # check if a new remote device
            if zb_data.destination_address[0]:
                for node in self.node_list:
                    if zb_data.destination_address[0] == node.addr_extended:
                        break
                else:
                    self._new_node(zb_data.destination_address[0])
                        
            if local_endpoint in self.rx_messages:
                if zb_data.source_address is None:
                    pass
                # create the tuple to store the message
                recv_tuple = (zb_data.payload, zb_data.source_address)
                #if endpoint is broadcast endpoint (0xFF), duplicate the message for all other endpoints
                if local_endpoint == 0xFF:
                    for endpoint_id in self.rx_messages:
                        if endpoint_id != 0:    #but don't give the message to the ZDO endpoint  #TTDO: is this correct?
                            self.rx_messages[endpoint_id].append(recv_tuple)
                else:
                    # add data to the message queue
                    self.rx_messages[local_endpoint].append(recv_tuple)
        elif message.API_ID in (IEEE_802_15_4_16_Data.rx_id, 
                                IEEE_802_15_4_64_Data.rx_id): # explicit 802.15.4 message
            #extract the message
            zb_data = message.api_data
            # make sure the address is registered, check with address = ""
            local_endpoint = zb_data.destination_address[1] #NOTE: will always be zero
            if local_endpoint in self.rx_messages:
                if zb_data.source_address is None:
                    pass
                # create the tuple to store the message
                recv_tuple = (zb_data.payload, zb_data.source_address)
                # add data to the message queue
                self.rx_messages[local_endpoint].append(recv_tuple)
        elif message.API_ID in (IEEE_802_15_4_16_IO.rx_id,
                                IEEE_802_15_4_64_IO.rx_id): # 802.15.4 IO message
            #extract the message
            io_data = message.api_data
            # NOTE: IO messages get passed out on endpoint 0 for 802.15.4
            if 0 in self.rx_messages:
                # create the tuple to store the message
                recv_tuple = (io_data.payload, io_data.source_address)
                # add data to the message queue
                self.rx_messages[0].append(recv_tuple)
        elif message.API_ID == Local_AT_Data.rx_id: #cmd ID for local AT response
            #extract the at_data
            at_data = message.api_data
            # check if this is the message we are waiting for
            if at_data.frame_id == AT_frame_id:
                return message
        elif message.API_ID == Remote_AT_Data.rx_id: #cmd ID for remote AT response
            #extract the at_data
            at_data = message.api_data
            # check if this is the message we are waiting for
            if at_data.frame_id == AT_frame_id:
                return message
        elif message.API_ID == ZigBee_Tx_Status_Data.rx_id or message.API_ID == IEEE_802_15_4_Tx_Status_Data.rx_id: #cmd ID for Tx Status message
            # match to 6th address parameter if enabled
            # extract the tx_response
            status_data = message.api_data
            if status_data.frame_id in self.tx_status:
                # Tx Status matches existing frame id, queue response in socket
                transaction_id, endpoint_id = self.tx_status[status_data.frame_id]
                delivery_status = chr(ZigBee_Tx_Status_Data.rx_id) + status_data.export()
                tx_status_tuple = (delivery_status, ("[00:00:00:00:00:00:00:00]!", endpoint_id, 0xC105, message.API_ID, 0, transaction_id))
                self.rx_messages[endpoint_id].append(tx_status_tuple)                                        
        else:
            # we are currently not handling this message type
            logger.debug("Not handling API message with ID %02X" % message.API_ID)

        return None


    def read_messages(self, AT_frame_id = 0, force_com=False):
        """Reads messages from the serial port, return message if it matches
        the AT_frame_id (meant to be used for AT commands)"""
        if not force_com and not com_port_opened:
            return None
        _global_lock.acquire(True)
        try:
            if self.serial is not None and self.serial.isOpen():
                self.rx_buffer += self.serial.read(self.serial.inWaiting()) #read everything that is available
            while 1:
                # sanitize buffer up to first candidate API frame:
                s_idx = self.rx_buffer.find('\x7e')
                if s_idx != -1:
                    self.rx_buffer = self.rx_buffer[s_idx:]
                message = API_Message() #create message and try to fill it from the serial port data.
                status = message.extract(self.rx_buffer)
                if status < 0:
                    # not enough buffer for the message
                    break
                # save off the message, may be used for XBS_PROT_XAPI
                message_buffer = self.rx_buffer[:status]
                # received frame, remove from buffer
                self.rx_buffer = self.rx_buffer[status:]
                if message.is_valid():
                    try:
                        return self.process_message(message, message_buffer, AT_frame_id, force_com)
                    except Exception, e:
                        logger.warning("exception during API message processing: %s" % str(e))
                else:
                    # Advance rx_buffer; useful in the case where ~~ appears in stream
                    # unexpectedly. It's been seeon on OSX a few times; likely due to faulty
                    # flow control. The message parser must advance in order to allow it to
                    # continue.
                    self.rx_buffer = self.rx_buffer[1:]
        finally:
            _global_lock.release()
        return None

    def register_joining_device(self, addr_extended, key, timeout = 0):
        "Register a device with the local XBee using a unique link key"
        #TTDO: keep track of timeout
        message = API_Message()
        message.api_data = Register_Device_Data(addr_extended, key)
        self.send(message)
        return True
    
    def unregister_joining_device(self, addr_extended, timeout = 0):
        "Unregister a device and its corresponding link key with the local XBee"
        #TTDO: keep track of timeout
        message = API_Message()
        message.api_data = Register_Device_Data(addr_extended)
        self.send(message)
        return True
    
    def ddo_get_param(self, addr_extended, id, timeout=1, order=False, force_com=False):
        "Get a Digi Device Objects parameter value (only local address currently supported)"
        _global_lock.acquire(True)
        try:
            if not force_com and not com_port_opened: #a global
                raise Exception("ddo_get_param: serial port not open")
            # check format of id
            if not isinstance(id, str):
                raise Exception("ddo_get_param() argument 2 must be string or read-only buffer, not " + str(id.type()))
            elif len(id) != 2:
                raise Exception("ddo_get_param: id string must be two characters!")
            # create message to send.
            message = API_Message()
            if addr_extended is None:
                message.api_data = Local_AT_Data(id)
                self.send(message)
            else:
                if not isinstance(addr_extended, str):
                    # TTDO: this should be type error
                    raise Exception("ddo_get_param: addr_extended must be a string or None.")
#                if len(addr_extended) != 26:
#                    #TTDO: should do better test of format...
#                    raise Exception("ddo_get_param: addr_extended format is invalid!")
                message.api_data = Remote_AT_Data(addr_extended, id)    
                self.send(message)            
            # wait to receive response
            AT_frame_id = message.api_data.frame_id
            at_response = None
            start_time = time.time()
            while start_time + timeout > time.time():
                at_response = self.read_messages(AT_frame_id, force_com = force_com)
                if at_response is not None:
                    break
            else:
                raise Exception("ddo_get_param: timeout fetching DDO parameter (%s@%s)." % (str(id), str(addr_extended)))
            return at_response.api_data.value
        finally:
            _global_lock.release()

    def ddo_set_param(self, addr_extended, id, value, timeout=1, order=False, apply=True):
        "Set a Digi Device Objects parameter value"
        _global_lock.acquire(True)
        try:
            if not com_port_opened: #a global
                raise Exception("ddo_set_param: serial port not opened")
            # check format of id
            if not isinstance(id, str):
                # TTDO: this should be a type error
                raise Exception("ddo_set_param() argument 2 must be string or read-only buffer, not " + str(id.type()))
            elif len(id) != 2:
                raise Exception("ddo_set_param: id string must be two characters!")
            # convert integer values to a string
            if isinstance(value, int) or isinstance(value, long):
                value_str = "" 
                # convert to big endian string representation
                while value > 0:
                    value_str = chr(value & 0xFF) + value_str
                    value /= 0x100
                if value_str == "":
                    # default to zero 
                    value_str = chr(0)
                value = value_str
                        
            # create message to send.
            message = API_Message()
            if addr_extended is None:
                message.api_data = Local_AT_Data(id, value)    
                self.send(message)
            else:
                if not isinstance(addr_extended, str):
                    # TTDO: this should be type error
                    raise Exception("ddo_set_param: addr_extended must be a string or None.")
                if len(addr_extended) != 24 and len(addr_extended) != 26: # depends on "[" and "]"
                    #TTDO: should do better test of format...
                    raise Exception("ddo_set_param: addr_extended format is invalid!")
                message.api_data = Remote_AT_Data(addr_extended, id, value)    
                self.send(message)
            
            # wait to receive response
            AT_frame_id = message.api_data.frame_id
            at_response = None
            start_time = time.time()
            while start_time + timeout > time.time():
                at_response = self.read_messages(AT_frame_id)
                if at_response is not None:
                    break
            else:
                raise Exception("ddo_set_param: timeout setting DDO parameter (%s@%s)." % (str(id), str(addr_extended))) # on timeout or error
            
            if at_response.api_data.status == 0:
                # success
                return True
            else:
                raise Exception("ddo_set_param: error setting DDO parameter (%s@%s)." % (str(id), str(addr_extended)))
            return False
        finally:
            _global_lock.release()
            
    def ddo_command(self, addr_extended, id, param=None, timeout=1, order=False, apply=True):
        "Execute a Digi Device Objects AT command (only local address currently supported)"
        _global_lock.acquire(True)
        try:
            if not com_port_opened: #a global
                raise Exception("ddo_command: serial port not opened")
            # check format of id
            if not isinstance(id, str):
                # TTDO: this should be a type error
                raise Exception("ddo_command() argument 2 must be string or read-only buffer, not " + str(id.type()))
            elif len(id) != 2:
                raise Exception("ddo_command: id string must be two characters!")
            # convert integer values to a string
            if isinstance(param, int) or isinstance(param, long):
                param_str = ""
                # convert to big endian string representation
                while param > 0:
                    param_str = chr(param & 0xFF) + param_str
                    param /= 0x100
                if param_str == "":
                    # default to zero 
                    param_str = chr(0)
                param = param_str
            elif param is None:
                param = ""
                        
            # create message to send.
            message = API_Message()
            if addr_extended is None:
                message.api_data = Local_AT_Data(id, param)
                self.send(message)
            else:
                if not isinstance(addr_extended, str):
                    # TTDO: this should be type error
                    raise Exception("ddo_command: addr_extended must be a string or None.")
                if len(addr_extended) != 24 and len(addr_extended) != 26: # depends on "[" and "]"
                    #TTDO: should do better test of format...
                    raise Exception("ddo_command: addr_extended format is invalid!")
                message.api_data = Remote_AT_Data(addr_extended, id, param)
                self.send(message)

            # wait to receive response
            AT_frame_id = message.api_data.frame_id
            at_response = None
            start_time = time.time()
            while start_time + timeout > time.time():
                at_response = self.read_messages(AT_frame_id)
                if at_response is not None:
                    break
            else:
                raise Exception("ddo_command: timeout performing DDO command (%s@%s)." % (str(id), str(addr_extended)))
            if at_response.api_data.status == 0:
                if len(at_response.api_data.value) == 0:
                    return None
                else:
                    return at_response.api_data.value
            else:
                raise Exception("ddo_command: error performing DDO command (%s@%s)." % (str(id), str(addr_extended)))
        finally:
            _global_lock.release()
    
    def get_node_list(self, refresh=True, blocking=True):
        "Perform a node discovery (blocking when refresh == True)"
        _global_lock.acquire(True)
        try:
            # Add local node to table if not already there
            if len(self.node_list) == 0:
                self.node_list.append(self._create_local_node())
            
            if refresh:
                if self.is_802_15_4():
                    # Node discover using the ND command on the XBee
                    nt_str = ddo_get_param(None, "NT")
                    # support 1 or 2 byte return
                    if len(nt_str) == 1:
                        nt, = struct.unpack(">B", nt_str)
                    elif len(nt_str) == 2:
                        nt, = struct.unpack(">H", nt_str)
                    else:
                        nt = 0xFF
                    node_discovery_timeout = nt / 10.0 # in seconds
                    response_list = []
                    # start Node discovery
                    message = API_Message()
                    message.api_data = Local_AT_Data("ND")    
                    self.send(message)            
                    # wait to receive responses
                    AT_frame_id = message.api_data.frame_id
                    at_response = None
                    start_time = time.time()
                    while start_time + node_discovery_timeout > time.time():
                        at_response = self.read_messages(AT_frame_id)
                        if at_response is not None:
                            # store responses for parsing later.
                            response_list.append(at_response)
                    # parse responses
                    self.node_list = self.node_list[1:] #remove all but the first item (local node)
                    device_types = ["coordinator", "router", "end"]
                    for at_response in response_list:
                        msg = at_response.api_data.value
                        if self.is_802_15_4():
                            addr_short, addr_extended, rssi = struct.unpack(">HQB", msg[:11])
                            index = 11
                        else:
                            addr_short, addr_extended = struct.unpack(">HQ", msg[:10])
                            index = 10
                        # convert 16-bit address into a formatted string
                        addr_short = short_to_address_string(addr_short)
                        # convert 64-bit address into a formatted string
                        addr_extended = MAC_to_address_string(addr_extended)
                        label = ""
                        for character in msg[index:]:
                            if character != chr(0):
                                label += character
                            else:
                                break
                        if self.is_802_15_4():
                            self.node_list.append(Node(device_types[1], addr_extended, addr_short, 0xFFFE, 0xC105, 0x101E, label))
                        else:
                            index += len(label) + 1
                            addr_parent, radio_type, status, profile_id, manufacturer_id = struct.unpack(">HBBHH", msg[index:index + 8])
                            # turn type into a string
                            radio_type = device_types[radio_type]
                            self.node_list.append(Node(radio_type, addr_extended, addr_short, addr_parent, profile_id, manufacturer_id, label))
                else:
                    # send request to own neighbor table to start discovery
                    for node in self.node_list:
                        LQI_aggregator(self.lqi_cluster, node.addr_extended, 0, self._LQI_callback)
                    self.node_list = self.node_list[:1] #remove all but the first item (local node)
                    
                    start_time = time.time()
                    while time.time() < start_time + 3: #NOTE: used to be 6.625 (as measured on CPX2)
                        self.read_messages()
                        if not blocking:
                            break
                        time.sleep(.1)
                                  
            return self.node_list[:]
        finally:
            _global_lock.release()
        
    def _create_local_node(self):
        """Create Node object based on local device"""
        # first time calling get_node_list, lets get the local data as well.
        at_my = self.ddo_get_param(None, "my")                
        addr_short = short_to_address_string(struct.unpack(">H", at_my)[0])
        at_sh = self.ddo_get_param(None, "sh")
        at_sl = self.ddo_get_param(None, "sl")
        
        addr_extended = MAC_to_address_string(struct.unpack(">Q", at_sh + at_sl)[0], 8)
        at_vr = self.ddo_get_param(None, "vr")
        VR = struct.unpack(">H", at_vr)[0]

        if VR & 0xF000 == 0x3000:
            # this is a smart energy device, no NI string
            label = ""
        else:
            label = self.ddo_get_param(None, "ni")
        
        #default parent to None
        addr_parent = "[FFFE]!"
        dtype = self.device_types[1] #default to router
        if not self.is_802_15_4(): #802.15.4 doesn't have parents.
            if VR & 0x0F00 == 0x0100:
                # this is a Coordinator
                dtype = self.device_types[0]
            elif VR & 0x0F00 == 0x0300:
                # this is a Router
                dtype = self.device_types[1]
            elif VR & 0x0F00 == 0x0400:
                # this is a Range Extender, device type is Router though
                dtype = self.device_types[1]
            else:
                #this is an End Device
                dtype = self.device_types[2]
                # only available on End Devices
                at_mp = self.ddo_get_param(None, "mp")
                addr_parent = short_to_address_string(struct.unpack(">H", at_mp)[0])
        return Node(dtype, addr_extended, addr_short, addr_parent, self.DIGI_PROFILE_ID, self.DIGI_MANUFACTURER_ID, label)                

    def _new_node(self, addr_extended, addr_short="[FFFE]!", node_type="unknown"):
        "Create new node in list and kick off LQI request"
        new_node = Node(type = node_type,\
                        addr_extended  = addr_extended,\
                        addr_short = addr_short)
        self.node_list.append(new_node)
        LQI_aggregator(self.lqi_cluster, addr_extended, 0, self._LQI_callback)
    
    def _LQI_callback(self, record_list):
        """callback for LQI aggregator on a Device"""
        #print "LQI final callback called"
        for record in record_list:
            for node in self.node_list:
                if record.addr_extended == node.addr_extended:
                    # already have a reference to this node...
                    node.addr_short = record.addr_short
                    break
            else:
                #construct a new lqi_aggregator and add it as a node
                self._new_node(record.addr_extended, record.addr_short, self.device_types[record.device_type])
    
    def device_announce_handler(self, record):
        """callback for device announce"""
        addr_short = short_to_address_string(record.nwk_addr)
        addr_extended = MAC_to_address_string(record.IEEE_addr)
        for node in self.node_list:
            if addr_extended == node.addr_extended:
                # already have a reference to this node...
                node.addr_short = addr_short
                break
        else:
            #construct a new lqi_aggregator and add it as a node
            self._new_node(addr_extended, addr_short)
        
# Create local XBee to refer to by default
default_xbee = XBee()
"XBee that communication defaults to (would be the only XBee on a ConnectPort)" 

def register_joining_device(addr_extended, key, timeout = 0):
    """register_joining _device(addr_extended, key[, timeout])->None"""
    return default_xbee.register_joining_device(addr_extended, key, timeout)

def unregister_joining_device(addr_extended, timeout = 0):
    """register_joining _device(addr_extended[, timeout])->None"""
    return default_xbee.unregister_joining_device(addr_extended, timeout)

def ddo_get_param(*params, **keywords):
    "Get a Digi Device Objects parameter value (only local address currently supported)"
    _global_lock.acquire(True)
    try:
        return default_xbee.ddo_get_param(*params, **keywords)
    finally:
        _global_lock.release()

def ddo_set_param(*params, **keywords):
    "Set a Digi Device Objects parameter value (only local address currently supported)"
    _global_lock.acquire(True)
    try:
        return default_xbee.ddo_set_param(*params, **keywords)
    finally:
        _global_lock.release()
        
def ddo_command(*params, **keywords):
    "Execute a Digi Device Objects AT command (only local address currently supported)"
    _global_lock.acquire(True)
    try:
        return default_xbee.ddo_command(*params, **keywords)
    finally:
        _global_lock.release()


def getnodelist(refresh = True):
    """get_node_list([refresh=True]) -> (node, node, ..., node)
    Perform a node discovery and return a tuple of nodes.
    If the refresh parameter is set to True this function will
    block and a fresh network discovery will be performed.
    If the refresh parameter is set to False this function will
    return a cached copy of the discovery list.  This cached
    version may include devices which were unable to respond
    within the discovery timeout imposed during a blocking call."""
    _global_lock.acquire(True)
    try:
        return default_xbee.get_node_list(refresh)
    finally:
        _global_lock.release()

# second name for getting a node list
get_node_list = getnodelist        
"""getnodelist([refresh=True]) -> (node, node, ..., node)
Alias for get_node_list; see get node_list for more
documentation."""
  
# Constants for the socket class
socket.AF_XBEE = 98
__register_with_socket_module("AF_XBEE")    
socket.AF_ZIGBEE = 98
__register_with_socket_module("AF_ZIGBEE")    
socket.XBS_PROT_APS = 81    
__register_with_socket_module("XBS_PROT_APS")
socket.XBS_PROT_TRANSPORT = 80
__register_with_socket_module("XBS_PROT_TRANSPORT")
socket.MSG_DONTWAIT = 128
__register_with_socket_module("MSG_DONTWAIT")
socket.XBS_PROT_XAPI = 84
__register_with_socket_module("XBS_PROT_XAPI")


# address socket option
socket.XBS_OPT_TX_NOACK = 0x01
"Disable end-to-end acknowledgement of frame."
__register_with_socket_module("XBS_OPT_TX_NOACK") 
socket.XBS_OPT_TX_PURGE = 0x10
"Purge the packet if delayed due to duty cycle (XB868DP only)."
__register_with_socket_module("XBS_OPT_TX_PURGE") 
socket.XBS_OPT_TX_APSSEC = 0x20
"Enable APS end-to-end security for this packet."
__register_with_socket_module("XBS_OPT_TX_APSSEC") 
socket.XBS_OPT_RX_ACK = 0x01
"Packet was acknowledged."
__register_with_socket_module("XBS_OPT_RX_ACK") 
socket.XBS_OPT_RX_BCADDR = 0x02
"Packet was received from broadcast address"
__register_with_socket_module("XBS_OPT_RX_BCADDR") 
socket.XBS_OPT_RX_APSSEC = 0x20
"Packet was received with APS end-to-end security enabled."
__register_with_socket_module("XBS_OPT_RX_APSSEC")     
# XBS_OPT_TX_NOREPEAT  - Don't repeat this packet
# XBS_OPT_TX_BCPAN     - Send to broadcast PAN
# XBS_OPT_TX_TRACERT   - Invoke traceroute
# XBS_OPT_RX_BCPAN     - Packet received on broadcase PAN


# socket option constants
socket.XBS_SOL_ENDPOINT = 65562
__register_with_socket_module("XBS_SOL_ENDPOINT")
socket.XBS_SOL_EP = socket.XBS_SOL_ENDPOINT
__register_with_socket_module("XBS_SOL_EP")
socket.XBS_SOL_APS = 65563
__register_with_socket_module("XBS_SOL_APS")
# SOL_SOCKET parameters
socket.SO_NONBLOCK = 0
__register_with_socket_module("SO_NONBLOCK")
# XBS_SOL_ENDPOINT / XBS_SOL_EP parameters
socket.XBS_SO_EP_FRAMES_TX = 16385
__register_with_socket_module("XBS_SO_EP_FRAMES_TX")
socket.XBS_SO_EP_FRAMES_RX = 16386
__register_with_socket_module("XBS_SO_EP_FRAMES_RX")
socket.XBS_SO_EP_TX_STATUS = 20482
__register_with_socket_module("XBS_SO_EP_TX_STATUS")    
# XBS_SOL_APS parameters

class Node:
    "An object returned from a node discovery"
    
    def __init__(self, type = None, addr_extended = None, addr_short = None, addr_parent = None, profile_id = 0, manufacturer_id = 0, label = None):
        self.type = type
        """The node type ("coordinator", "router", or "end")"""
        self.addr_extended = addr_extended
        "64-bit colon-delimited extended hardware address"
        self.addr_short = addr_short
        "16-bit network assigned address"
        if addr_parent is None:
            addr_parent = "[FFFE]!"
        self.addr_parent = addr_parent
        "16-bit network parent address"
        self.profile_id = profile_id
        "node profile ID"
        self.manufacturer_id = manufacturer_id
        "node manufacturer ID"
        self.label = label
        "the nodes string label"

    def to_socket_addr(self, endpoint, profile_id, cluster_id, use_short):
        "Transform a node into a socket address tuple"
        if use_short:
            return [MAC_to_address_string(self.addr_short, 2), endpoint, profile_id, cluster_id]
        else:
            return [MAC_to_address_string(self.addr_extended), endpoint, profile_id, cluster_id]

    def __str__(self):
        "Print only the type and address of the node"
        return "<node type=%s addr_extended=%s>" % (self.type, self.addr_extended)

#
# socket and select keyword redirect
#
# The following is a bit of Python trickery that replaces functions in the socket and select modules
# with functions in the zigbee module.  This allows functions calls like socket.socket() or select.select()
# to actually call zigbee.XBeeSocket and zigbee.xbee_select().

original_select = select.select
"Storage for the non-XBee type of Python select"
SELECT_SLEEP_TIME = 0.05
"Time to sleep in seconds between polls of the sockets"

def xbee_select(rlist, wlist, xlist, timeout = None):
    "Select which sockets are ready to read, write, and have exceptions"

    start_time = None
    if timeout is not None:
        start_time = time.time()

    # various list variables
    rlist_nonxbee = []
    wlist_nonxbee = []
    xlist_nonxbee = []
    rlist_xbee = []
    wlist_xbee = []
    rlist_out = []
    wlist_out = []
    xlist_out = []
  
    # split xbee and non-xbee sockets
    for sock in rlist:
        try:
            if sock._family == socket.AF_XBEE:   
                rlist_xbee.append(sock)
            else:
                rlist_nonxbee.append(sock)
        except:
            rlist_nonxbee.append(sock)
    for sock in wlist:
        try:
            if sock._family == socket.AF_XBEE:   
                wlist_xbee.append(sock)
            else:
                wlist_nonxbee.append(sock)
        except:
            wlist_nonxbee.append(sock)
    for sock in xlist:
        try:
            if sock._family != socket.AF_XBEE:   
                xlist_nonxbee.append(sock)
        except:
            xlist_nonxbee.append(sock)


    # use the original select if no xbee sockets
    if not len(rlist_xbee) and not len(wlist_xbee): 
        return original_select(rlist_nonxbee, wlist_nonxbee, xlist_nonxbee, timeout)
    
    # flag if there are any non_xbee sockets
    nonxbee_socket = len(rlist_nonxbee) or len(wlist_nonxbee) or len(xlist_nonxbee)
    
    # loop over xbee and non-xbee sockets
    first_loop = True
    while first_loop or timeout is None or start_time + timeout >= time.time():
        if first_loop:
            # immediately check for matches on the first loop
            first_loop = False
        else:
            # on subsequent loops, sleep between polls.
            if timeout is not None:
                time.sleep(min(SELECT_SLEEP_TIME,
                               abs(start_time + timeout - time.time())))
            else:
                time.sleep(SELECT_SLEEP_TIME)
            
        # check original sockets
        if nonxbee_socket:
            rlist_out, wlist_out, xlist_out = original_select(rlist_nonxbee, wlist_nonxbee, xlist_nonxbee, 0)
        
        # check XBee sockets
        for sock in rlist_xbee:
            _global_lock.acquire(True)
            try:
                if sock._pending_message():
                    rlist_out.append(sock)
            finally:
                _global_lock.release()  
        # xbee sockets are always ready for write
        #TODO: check to make sure serial port is open and ready to go.
        wlist_out.extend(wlist_xbee)
    
        # check for any matches
        if len(rlist_out) or len(wlist_out) or len(xlist_out):
            break
    
    return  rlist_out, wlist_out, xlist_out

# replace the original select with the xbee select
select.select = xbee_select

# Save the original socket.socket definition:
original_socket = socket.socket

class XBeeSocket(original_socket):
    """Extend socket.socket with XBee emulation hooks."""
    def __init__(self, family=socket.AF_INET, type=socket.SOCK_STREAM,
                 proto=0, _sock=None, xbee=default_xbee):
        if family == socket.AF_XBEE:
            self.__xb_init(family, type, proto, xbee)
        else:
            original_socket.__init__(self, family, type, proto, _sock)            

    def __xb_init(self, family, type, proto, xbee):
        self._family = family
        self._type = type
        if proto is None:
            proto = socket.XBS_PROT_APS
        self._proto = proto
        self.xbee = xbee
        self.endpoint_id = None
        # initialize the socket options
        self.options = {}
        # SOL_SOCKET
        self.options[socket.SOL_SOCKET] = {  
                                            socket.SO_NONBLOCK: 0 # SO_NONBLOCK
                                            }
        # XBS_SOL_ENDPOINT
        self.options[socket.XBS_SOL_ENDPOINT] = {
                                                 socket.XBS_SO_EP_TX_STATUS: 0
                                                 }
        # XBS_SOL_APS
        self.options[socket.XBS_SOL_APS] = {}
        self.closed = True
        
        # rebind external methods:
        self.__del__ = self._xb___del__
        self.close = self._xb_close
        self.getsockopt = self._xb_getsockopt
        self._pending_message = self._xb__pending_message
        self.recvfrom = self._xb_recvfrom
        self.sendto = self._xb_sendto
        self.setsockopt = self._xb_setsockopt
        self.bind = self._xb_bind
        self.setblocking = self._xb_setblocking
        self.debug_add_message = self._xb_debug_add_message

        
    def _xb___del__(self):
        "Delete the socket"
        self.close()

    def _xb_close(self):
        "Close the socket"
        if not self.closed:
            # remove self from xbee
            self.xbee.unregister_endpoint(self.endpoint_id)
        self.closed = True
        
    def _xb_getsockopt(self, level, optname):
        "Get socket options"
        if level in self.options and optname in self.options[level]:
                return self.options[level][optname]
        return None

    def _xb__pending_message(self):
        "Check to see if there is a message ready"
        self.xbee.read_messages()
        if self.endpoint_id is None:
                raise Exception("Socket is not yet bound to endpoint")
        if self.closed:
            raise Exception("Socket is closed")
        message_list = self.xbee.rx_messages.get(self.endpoint_id)
        if message_list is None:
            # try to re-register endpoint with XBee
            self.xbee.register_endpoint(self.endpoint_id)
            return 0
        else:
            return len(self.xbee.rx_messages[self.endpoint_id])
            
    def _xb_recvfrom(self, buflen, flags = 0):
        "Receive a message from the socket."
        nonblocking = False
        if flags == socket.MSG_DONTWAIT or self.getsockopt(socket.SOL_SOCKET, socket.SO_NONBLOCK):
            nonblocking = True
        if self.endpoint_id is None:
            raise Exception("error: socket not bound yet") #Note: this is a different error
        while (1):
            payload, address = self.xbee.recv(self.endpoint_id)
            if payload is not None:
                return payload[:buflen], address
            elif nonblocking:
                return None, None
        
    def _xb_sendto(self, data, flags, addr = None):
        "Send a message from a socket"
        if addr is None:
            addr = flags
            flags = 0
        #TTDO: Should support the MSG_DONTWAIT flag and do a blocking call.
        if self.endpoint_id is not None and self.endpoint_id >= 0:
            self.xbee.send_zb(self.endpoint_id, addr, data)
        return len(data)
    
    def _xb_setsockopt(self, level, optname, value):
        "Set socket options"
        if level in self.options and optname in self.options[level]:
                self.options[level][optname] = value 
        #TTDO: figure out the return value
    
    def _xb_bind(self, address):
        "Bind a socket to an address"
        if self.endpoint_id is not None:
            # socket already bound to an endpoint
            raise("error: (22, 'Invalid argument')")
        # only look at endpoint from address
        endpoint_id = address[1]
        # if this is a XBS_PROT_XAPI socket (which gets specific API frames), use a negative endpoint ID
        if self._proto == socket.XBS_PROT_XAPI:
            endpoint_id = -endpoint_id
        # make sure there isn't already a socket bound to this endpoint.
        if endpoint_id in self.xbee.rx_messages:
            raise Exception("error: socket already bound on this address")
        else:
            # add the address
            self.xbee.register_endpoint(endpoint_id)
        # set the endpoint locally
        self.endpoint_id = endpoint_id
        self.closed = False            
        return 0
        
    def _xb_setblocking(self, value):
        "Set the socket to be blocking or non-blocking"
        return self.setsockopt(socket.SOL_SOCKET, socket.SO_NONBLOCK, not value)

    def _xb_debug_add_message(self, payload, source_address):
        "Debugging function to artificially add an incoming message to a socket"
        # create the tuple to store the message
        recv_tuple = (payload, source_address)
        # add data to the message queue
        self.xbee.rx_messages[self.endpoint_id].append(recv_tuple)
        
# replace the original socket with the xbee_socket
socket.socket = XBeeSocket
# NOTE: SocketType will not be changed and will still refer to the non-XBee socket class.

# If socketpair isn't defined in socket, define one:
if 'socketpair' not in socket.__dict__:
    import threading
    def _socketpair(family=socket.AF_INET, type_=
                    socket.SOCK_STREAM, proto=socket.IPPROTO_IP):
        """Wraps socketpair() to support Windows using local ephemeral ports"""
        
        def _pair_connect(sock, port):
            sock.connect( ('localhost', port) )
    
        listensock = XBeeSocket(family, type_, proto)
        listensock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listensock.bind( ('localhost', 0) )
        iface, ephport = listensock.getsockname()
        listensock.listen(1)

        sock1 = XBeeSocket(family, type_, proto)
        connthread = threading.Thread(target=_pair_connect,
                                      args=[sock1, ephport])
        connthread.setDaemon(1)
        connthread.start()
        sock2, sock2addr = listensock.accept()
        listensock.close()
        return (sock1, sock2)

    socket.socketpair = _socketpair


original_getaddrinfo = socket.getaddrinfo

def getaddrinfo(host, port, family=0, socktype=0, proto=0, flags=0):
    import re
    
    af_xb_re = re.compile("(\\[?([0-9a-f]{2}:){7}[0-9a-f]{2}\\]?!)|" \
                          "(\\[?[0-9a-f]{4}\\]?!)", re.IGNORECASE)


    if host and af_xb_re.match(host) is not None:
        return [(socket.AF_XBEE, socket.SOCK_DGRAM,
                socket.XBS_PROT_TRANSPORT, host,
                (host, port, 0, 0))]

    return original_getaddrinfo(host, port, family, socktype, proto, flags)

socket.getaddrinfo = getaddrinfo

# initialize serial port
#this is done in a separate thread so that the rest of the program can continue to initialize however it can while the XBee is unavailable

import thread
import serial
import simulator_settings

#simple global to make sure that initial startup happens in expected order (if serial port is available it should be instantiated from the start)
ran_first_time = False

def open_com_thread():
    global com_port_opened
    global ran_first_time
    global default_xbee
    global _com_mgmt_lock
    while not com_port_opened:
        xbee_serial_port = None
        _com_mgmt_lock.acquire()
        try:
            if not simulator_settings.settings.get("com_port") or not simulator_settings.settings.get("baud"):
                #invalid serial port settings
                if not ran_first_time:
                    logger.error("Invalid serial port settings, COM port='%s', baud='%s'" % (simulator_settings.settings.get('com_port', 'No COM'), simulator_settings.settings.get('baud', 'no baud')))
                    ran_first_time = True             
                continue # will hit "finally" below
            try:
                xbee_serial_port = serial.Serial(simulator_settings.settings["com_port"], simulator_settings.settings["baud"], rtscts = 1)
                xbee_serial_port.writeTimeout = 1 # 1 second timeout for writes
                xbee_serial_port.flushInput() #get rid of anything the XBee had stored up
                default_xbee.serial = xbee_serial_port
                #make sure the serial port connects to an XBee (ddo will throw exception on error)
                default_xbee.set_version()
                # COM port successfully opened, finish initialization
                com_port_opened = True
                if simulator_settings.settings.get("xbee_initialization", True):
                    # initialize some critical XBee settings on behalf of the user:
                    try:
                        default_xbee.ddo_set_param(None, "D6", 1)
                        default_xbee.ddo_set_param(None, "D7", 1)
                    except Exception, e:
                        # Continue with opening XBee, this is NOT a fatal error.
                        logger.warning("unable to initialize XBee DDO params: %s" % repr(e))
                    try:
                        if not default_xbee.is_series_1():
                            # ATAO not supported on XBee series 1
                            default_xbee.ddo_set_param(None, "AO", 3)
                    except Exception, e:
                        logger.warning("unable to initialize XBee DDO params: %s" % repr(e))
                try:
                    default_xbee.get_node_list(refresh=True, blocking=False) #kick off discovery of nodes on network
                except Exception, e:
                    logger.warning("exception during XBee node discovery: %s" % e)
                logger.info("Serial port for XBee opened successfully (%s, %s)" % (simulator_settings.settings.get('com_port', 'No COM'), simulator_settings.settings.get('baud', 'no baud')))
                ran_first_time = True
                return
            except Exception, e:
                if not ran_first_time:
                    logger.error("Exception while creating serial port (%s, %s): %s" % (simulator_settings.settings.get('com_port', 'No COM'), simulator_settings.settings.get('baud', 'no baud'), e))
                    ran_first_time = True
                if xbee_serial_port:
                    xbee_serial_port.close()
        finally:
            if not com_port_opened:
                _com_mgmt_lock.release()
                time.sleep(.5)  #try opening the serial port again after a short sleep
            else:
                _com_mgmt_lock.release()

def com_port_changes(new_value, old_value):
    global com_port_opened
    global ran_first_time
    global default_xbee
    global _com_mgmt_lock
    _com_mgmt_lock.acquire()
    try:
        if com_port_opened:
            com_port_opened = False
            # close the com port
            default_xbee.close_serial()
            ran_first_time = False # we should reprint an error if the serial port settings don't work
            thread.start_new_thread(open_com_thread, ())
    finally:
        _com_mgmt_lock.release()

thread.start_new_thread(open_com_thread, ())

simulator_settings.settings.add_callback('com_port', com_port_changes)
simulator_settings.settings.add_callback('baud', com_port_changes)

# wait for the open_com_thread to run through the first time and try to open a COM port.
while not ran_first_time:
    time.sleep(0.001)
