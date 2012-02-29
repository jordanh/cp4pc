"""
Simple Diagnostic Tool for Xbee management on the connectport
"""
import zigbee
import struct
import sys

def s(id, value):
    """Short signature wrapper function for ddo_set_param"""
    return zigbee.ddo_set_param(None, id, value)
    
def g(id):
    """Short signature wrapper function for ddo_get_param"""
    return zigbee.ddo_get_param(None, id)

def exit():
    sys.exit()
    
def mac():
    sh,= struct.unpack(">I",g("SH"))
    sl,= struct.unpack(">I",g("SL"))
    print "MAC Address: 0x%04X%04X" % (sh, sl)

def chan():
    print "Channel: %d" % ord(g("CH"))

def pan():
    oi = g("OI")
    val = struct.unpack(">H", oi)
    print "Operating Pan ID: 0x%04X" % val

def join(seconds = None):
    if seconds is None:
        seconds = 0xFE
    s('NJ', 0x77)
    s('NJ', seconds)
    if seconds == 0:
        print "Node Joining Disabled"
    else:
        print "Node Joining Enabled for the next %d seconds" % seconds

def ao():
    ao = g("AO")
    strings = {}
    strings[1] = "AO: API Output Mode - Explicit (no passthru)"
    strings[3] = "AO: API Output Mode - Explicit with ZDO passthru"
    print strings[ord(ao)]

def baud():
    baud = g("BD")
    mults = [1,2,4,8,16,32,48,96]
    rates = [1200 * mults[x] for x in range(8)]
    print "Baud Rate: %d" % rates[struct.unpack(">I",baud)[0]]
    
mac() #print the mac address
chan()#print the channel
pan() #print the operating pan id

ao() #print the api output mode
join(0) #print the node join time
baud() #print the baud rate