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

# This file implements an ADDP client in Python.

import socket
import struct
import time
import string
import binascii
from simulator_settings import settings

ADDP_VERBOSE = 0 # set to 1 for debug output

ADDP_COOKIE = 0x44494749        # 'D', 'I', 'G', 'I'
ADDP_VERSION = 0x0200

# ADDP commands
ADDP_CMD_NULL = 0x0000
ADDP_CMD_CONF_REQ = 0x0001 # Request configuration parameters
ADDP_CMD_CONF_REPLY = 0x0002# Reply configuration parameters
ADDP_CMD_SET_ADDR = 0x0003# Configure network parameters
ADDP_CMD_SET_ADDR_REPLY = 0x0004# Reply to network config request
ADDP_CMD_REBOOT = 0x0005# Request device reboot
ADDP_CMD_REBOOT_REPLY = 0x0006# Reply to reboot request
ADDP_CMD_SET_DHCP = 0x0007# Request to enable/disable DHCP
ADDP_CMD_DHCP_REPLY = 0x0008# Reply to DHCP request   
ADDP_CMD_SET_EDP = 0x000B# Configure remote management
ADDP_CMD_EDP_REPLY = 0x000C# Configure remote management
#ADDP_CMD_SET_WL = 0x000?# Request to configure wireless
#ADDP_CMD_SET_WL_REPLY = 0x000?# Result of wireless operation
#ADDP_CMD_COUNTRY_LIST_REQ = 0x000?# Wireless country codes list
#ADDP_CMD_COUNTRY_LIST_REPLY = 0x000?# Result of country codes list

# ADDP OP Codes
ADDP_OP_PAD = 0x00 # NOP, used to align fields (0-byte)
ADDP_OP_MAC = 0x01 # MAC address (6-byte)
ADDP_OP_IPADDR = 0x02 # IP Address (4-byte)
ADDP_OP_SUBMASK = 0x03 # Subnet Mask (4-byte)
ADDP_OP_NAME = 0x04 # Unit Name (n-byte, no null-terminator)
ADDP_OP_DOMAIN = 0x05 # (deprecated in ADDPv2)
ADDP_OP_HWTYPE = 0x06 # (deprecated in ADDPv2)
ADDP_OP_HWREV = 0x07 # (deprecated in ADDPv2)
ADDP_OP_FEPREV = 0x08 # (deprecated in ADDPv2)
ADDP_OP_MSG = 0x09 # A message string (n-byte)
ADDP_OP_RESULT = 0x0a # Result code for an operation (1-byte)
ADDP_OP_GATEWAY = 0x0b # Default Gateway IP Address (4-byte)
ADDP_OP_ADVISORY = 0x0c # Advisory Information (2-byte)
ADDP_OP_HWNAME = 0x0d # Hardware name (n-byte)
ADDP_OP_REALPORT = 0x0e # (deprecated in ADDPv2)
ADDP_OP_DNS = 0x0f # DNS IP address (4-byte)
ADDP_OP_DHCP = 0x10 # DHCP Mode (1=on, 0=off)
ADDP_OP_ERRCODE = 0x11 # Result of operation (1-byte)
ADDP_OP_PORT_CNT = 0x12 # (deprecated in ADDPv2)
ADDP_OP_SECURE_REALPORT = 0x13 # (deprecated in ADDPv2)
ADDP_OP_VERSION = 0x14 # ADDP Version number (2-byte)
ADDP_OP_VENDOR_GUID = 0x15 # Vendor GUID (16-byte)
ADDP_OP_IF_TYPE = 0x16 # Interface Type (1-byte)
ADDP_OP_CHALLENGE = 0x17 # MD5 Challenge (14-byte)
ADDP_OP_VENDOR_DATA = 0x18 #

ADDP_OP_WL_SSID = 0xe0 # SSID (up to 32 bytes)
ADDP_OP_WL_AUTO_SSID = 0xe1 # Auto SSID mode (1=on, 0=off)
ADDP_OP_WL_TX_ENH_POWER = 0xe2 # Transmit enhance power
ADDP_OP_WL_AUTH_MODE = 0xe3 # Authentication mode (1=open, 2=PSK)
ADDP_OP_WL_ENC_MODE = 0xe4 # Encryption mode(1=none, 2=WEP40, 3=WEP128)
ADDP_OP_WL_ENC_KEY = 0xe5 # Encryption key (n-byte)
ADDP_OP_WL_CUR_COUNTRY = 0xe6 # Country code (2-byte)
ADDP_OP_WL_COUNTRY_LIST = 0xe7 # Country List (n-byte)

# values for ADDP_OP_RESULT
ADDP_SUCCESS = 0x00
ADDP_FAILURE = 0xFF

# socket parameters
ANY = '0.0.0.0'                               # Bind to all interfaces
MCAST_ADDR = "224.0.5.128"
MCAST_PORT = 2362
#ADDR_PORT = 1181

def mac_from_device_id(device_id):
    # device_id should be a string of the format: xxxxxxxx-xxxxxxxx-xxxxxxxx-xxxxxxxx
    # we want the last 12 hex digits
    hex_string = ""
    for ch in device_id:
        if ch in string.hexdigits:
            hex_string += ch
    return binascii.a2b_hex(hex_string[-16:-10] + hex_string[-6:])

class ADDP_Frame:
    def __init__(self, cmd = ADDP_CMD_NULL, payload = ""):
        self.cmd = cmd
        self.payload = payload
        
    def extract(self, buf):
        cookie, self.cmd, length = struct.unpack(">IHH", buf[:8])
        self.payload = buf[8:]
        # check cookie to make sure it matches "DIGI"
        if cookie != ADDP_COOKIE:
            raise Exception("Cookie didn't match, ignore message.")
        # make sure length is correct
        if length != len(buf) - 8: # 8 bytes in header
            raise Exception("Message length doesn't match.")
        
    def export(self):
        buf = struct.pack(">IHH", ADDP_COOKIE, self.cmd, len(self.payload))
        buf += self.payload
        return buf


class ADDP:
    
    def __init__(self):
        # create multicast socket to listen for ADDP requests
        self.input_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.input_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.input_sock.bind((ANY, MCAST_PORT))
        self.input_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
        self.input_sock.setsockopt(socket.IPPROTO_IP, 
                                   socket.IP_ADD_MEMBERSHIP, 
                                   socket.inet_aton(MCAST_ADDR) + socket.inet_aton(ANY))
        
        self.output_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)        
        self.mac = mac_from_device_id(settings.get("device_id", "00000000-00000000-00000000-00000000"))
        
    
    def run_forever(self):
        while 1:
            try:
                message, address = self.input_sock.recvfrom(8092)
                if ADDP_VERBOSE:
                    print "Got data from", address
                    print ["%02X"%ord(x) for x in message]
                # extract the header
                frame = ADDP_Frame()
                frame.extract(message)
        
                response = None
                # parse the rest of the message based on the command type
                if frame.cmd == ADDP_CMD_CONF_REQ:
                    response = self.addp_conf_req(frame)
                elif frame.cmd == ADDP_CMD_SET_EDP:
                    response = self.addp_set_edp(frame)
                elif frame.cmd == ADDP_CMD_REBOOT:
                    # TODO: add support for reboot?
                    if ADDP_VERBOSE:
                        "Received Reboot command - ignoring"
                    pass
                else:
                    raise Exception("Unknown frame cmd id=0x%04X" % frame.cmd)
                
                if response:
                    if ADDP_VERBOSE:
                        print "Sending response to: " + str(address)
                        print ["%02X" % ord(x) for x in response.export()]
                    self.output_sock.sendto(response.export(), address)
                
            except:
                pass        

    def addp_conf_req(self, frame):
        addp_ver = 0x0100 # ADDPv1, may be overwritten in command 
        mac_addr = frame.payload[:6]
        # check if mac_addr matches ours or is equal to broadcast MAC
        if mac_addr != "\xff\xff\xff\xff\xff\xff" and mac_addr != self.mac:
            raise Exception("Message is not for us.")
        index = 6
        # pull out any OP commands in frame
        while len(frame.payload) > index + 2:
            op_code, length = struct.unpack(">BB", frame.payload[index, index + 2])
            index += 2
            if op_code == ADDP_OP_VERSION:
                addp_ver, = struct.unpack(">H", frame.payload[index: index + 2])
                index += 2 
            else:
                # unsupported OP code
                index += length
        
        # Create response
        response = ADDP_Frame(ADDP_CMD_CONF_REPLY)
        
        # add MAC address
        response.payload += struct.pack(">BB", ADDP_OP_MAC, 6)
        response.payload +=self.mac
        # add IP address, submask, and gateway IP
        response.payload += struct.pack(">BBI", ADDP_OP_IPADDR, 4, 0x0A281276)
        response.payload += struct.pack(">BBI", ADDP_OP_SUBMASK, 4, 0xFFFFFF00)
        response.payload += struct.pack(">BBI", ADDP_OP_GATEWAY, 4, 0x0A281201)
        # add DNS servers
        response.payload += struct.pack(">BBI", ADDP_OP_DNS, 4, 0x0A28121A)
        response.payload += struct.pack(">BBI", ADDP_OP_DNS, 4, 0x0A28121C)
        # add DHCP settings (DHCP server or 0)
        response.payload += struct.pack(">BBI", ADDP_OP_DHCP, 4, 0x0A281240)
        # add device name
        device_name = settings.get('device_name', '')
        response.payload += struct.pack(">BB", ADDP_OP_NAME, len(device_name))
        response.payload += device_name
        # add hardware name
        device_type = settings.get('device_type')
        response.payload += struct.pack(">BB", ADDP_OP_HWNAME, len(device_type))
        response.payload += device_type
        
        if addp_ver == 0x0100:        
            # add version
            # get the time of when the program was started
            (year, mon, mday, hour, min, sec, wday, yday, isdst) = time.gmtime(time.time() - time.clock())
            version = "Version %s %d/%02d/%d" % (settings.get('version', '0.0.0'), mon, mday, year)
            response.payload += struct.pack(">BB", ADDP_OP_FEPREV, len(version))
            response.payload += version
        
        return response
    
    def addp_set_edp(self, frame):
        edp_enabled, edp_length = struct.unpack(">BB", frame.payload[:2])
        edp_url = frame.payload[2:edp_length+2] 
        print "EDP URL = " + edp_url
        mac_addr = frame.payload[edp_length+2:edp_length+8]
        
        # check if mac_addr matches ours or is equal to broadcast MAC
        if mac_addr != "\xff\xff\xff\xff\xff\xff" and mac_addr != self.mac:
            if ADDP_VERBOSE:
                print "Message is not for us."
            return None
        
        # Create response
        response = ADDP_Frame(ADDP_CMD_EDP_REPLY)
        # add MAC address
        response.payload += struct.pack(">BB", ADDP_OP_MAC, 6)
        response.payload += self.mac
        # add result of success
        response.payload += struct.pack(">BBB", ADDP_OP_RESULT, 1, ADDP_SUCCESS)    
        # add success message?
        
        #ADDP_OP_ERRCODE
        #ADDP_OP_MSG
        
        return response

            