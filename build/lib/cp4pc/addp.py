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

# This file implements an ADDP client in Python.

import socket
import select
import struct
import time
import logging
import threading

from simulator_settings import settings

# set up logger
logger = logging.getLogger("cp4pc.addp")
logger.setLevel(logging.INFO)

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


class ADDP(threading.Thread):
    
    def __init__(self):
        threading.Thread.__init__(self)
        threading.Thread.setDaemon(self,True)
        # create multicast sockets to listen for ADDP requests
        self.socks = {} # dict of {socket: ip}
        self.setup_socks()
        self.mac = struct.pack("!Q", settings['mac'])[2:]
    
    def setup_socks(self):
        # populate list of sockets
        ip_list = [] #use this to remove sockets that are no longer active.
        for interface_tuple in socket.getaddrinfo(None, MCAST_PORT, socket.AF_INET, socket.SOCK_DGRAM, 0, socket.AI_PASSIVE): # family, socktype, proto, canonname, sockaddr
            ip_address = interface_tuple[4][0]
            ip_list.append(ip_address)
            if ip_address not in self.socks.values():
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((ip_address, MCAST_PORT))
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(MCAST_ADDR) + socket.inet_aton(ANY))
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1) #turn on loopback
                self.socks[sock] = ip_address
        # remove sockets that are no longer valid
        for ip in self.socks.values():
            if ip not in ip_list:
                self.socks.remove(ip)

    def run(self):
        while 1:
            try:
                rlist = select.select(self.socks.keys(), [], [], 5)[0] # listen for incoming messages
                
                # check for new interface
                self.setup_socks()
                
                if not rlist:
                    continue # go back to waiting for messages
                
                message, address = rlist[0].recvfrom(4096) #don't expect larger ADDP packets than this...
                logger.debug("Received message from: ", address)
                #print ["%02X"%ord(x) for x in message]
                
                # extract the header
                frame = ADDP_Frame()
                frame.extract(message)
                
                # get IP from self.socks and convert to integer
                local_ip = 0
                for num in (int(x, 10) for x in self.socks[rlist[0]].split('.')):
                    local_ip = local_ip * 0x100 + num
                local_mac = self.mac #NOTE: MAC will not match interface (may update in the future).
                
                response = None
                # parse the rest of the message based on the command type
                if frame.cmd == ADDP_CMD_CONF_REQ:
                    response = self.addp_conf_req(frame, address, local_ip, local_mac)
                elif frame.cmd == ADDP_CMD_SET_EDP:
                    response = self.addp_set_edp(frame, address, local_ip, local_mac)
                elif frame.cmd == ADDP_CMD_REBOOT:
                    logger.warning("Ignoring received to reboot")
                    pass
                else:
                    raise Exception("Unknown frame cmd id=0x%04X" % frame.cmd)
                
                if response:
                    logger.debug("Sending response to: " + str(address))
                    #print ["%02X" % ord(x) for x in response.export()]
                    rlist[0].sendto(response.export(), address)
                
            except Exception, e:
                logger.error("Exception: %s"%e)

    def addp_conf_req(self, frame, address, local_ip, local_mac):
        addp_ver = 0x0100 # ADDPv1, may be overwritten in command 
        mac_addr = frame.payload[:6]
        # check if mac_addr matches ours or is equal to broadcast MAC
        if mac_addr != "\xff\xff\xff\xff\xff\xff" and mac_addr != local_mac:
            logger.debug("Message has wrong address.")
            return None
        index = 6
        logger.info("Received 'Configuration' request from: %s" % str(address))
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
        response.payload += self.mac
        # add IP address, submask, and gateway IP
        response.payload += struct.pack(">BBI", ADDP_OP_IPADDR, 4, local_ip)
        #NOTE: add more parameters to response (Python netifaces module would work well for this).
        #response.payload += struct.pack(">BBI", ADDP_OP_SUBMASK, 4, 0x00000000)
        #response.payload += struct.pack(">BBI", ADDP_OP_GATEWAY, 4, 0x00000000)
        # add DNS servers
        #response.payload += struct.pack(">BBI", ADDP_OP_DNS, 4, 0x00000000)
        #response.payload += struct.pack(">BBI", ADDP_OP_DNS, 4, 0x00000000)
        # add DHCP settings (DHCP server or 0)
        #response.payload += struct.pack(">BBI", ADDP_OP_DHCP, 4, 0x00000000)
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
    
    def addp_set_edp(self, frame, address, local_ip, local_mac):
        edp_enabled, edp_length = struct.unpack(">BB", frame.payload[:2])
        edp_url = frame.payload[2:edp_length+2] 
        logger.warning("Ignoring request to set EDP URL = " + edp_url)
        mac_addr = frame.payload[edp_length+2:edp_length+8]
        
        # check if mac_addr matches ours or is equal to broadcast MAC
        if mac_addr != "\xff\xff\xff\xff\xff\xff" and mac_addr != local_mac:
            logger.debug("Message has wrong address.")
            return None
        
        logger.info("Received 'Set EDP' request from: %s" % str(address))        
        # Create response
        response = ADDP_Frame(ADDP_CMD_EDP_REPLY)
        # add MAC address
        response.payload += struct.pack(">BB", ADDP_OP_MAC, 6)
        response.payload += local_mac
        # add result of success
        response.payload += struct.pack(">BBB", ADDP_OP_RESULT, 1, ADDP_SUCCESS)    
        # add success message?
        
        #ADDP_OP_ERRCODE
        #ADDP_OP_MSG
        
        return response

            
