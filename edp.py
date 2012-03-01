import socket
import select
import time
import struct
import string
import logging
from errno import *

from simulator_settings import settings

# Basic, comm layer types.
EDP_VERSION         = 0x0004
EDP_VERSION_OK      = 0x0010
EDP_VERSION_BAD     = 0x0011
EDP_SERVER_OVERLOAD = 0x0012
EDP_KEEPALIVE       = 0x0030
EDP_PAYLOAD         = 0x0040

# Facility codes
EDP_FACILITY_PIO        = 0x0000
EDP_FACILITY_FILESYSTEM = 0x0040
EDP_FACILITY_FIRMWARE   = 0x0070
EDP_FACILITY_RCI        = 0x00A0

EDP_FACILITY_CLIENT_LOOPBACK = 0xFF00
EDP_FACILITY_SERVER_LOOPBACK = 0xFF01
EDP_FACILITY_CONN_CONTROL    = 0xFFFF

# Interval in seconds
EDP_KEEPALIVE_INTERVAL = 16
EDP_KEEPALIVE_WAIT = 3

# frequency to retry connections to iDigi server
RECONNECT_TIME = 60

# RCI constants
RCI_COMMAND_REQ_START   = 0x01
RCI_COMMAND_REQ_DATA    = 0x02
RCI_COMMAND_REQ_END     = 0x03
RCI_COMMAND_REPLY_START = 0x04
RCI_COMMAND_REPLY_DATA  = 0x05
RCI_COMMAND_REPLY_END   = 0x06
RCI_ERROR_DETECTED      = 0xE0
RCI_ERROR_FATAL         = 0x01
RCI_ERROR_TIMEOUT       = 0x02
RCI_ERROR_COMPR         = 0x03
RCI_ERROR_DECOMPR       = 0x04
RCI_ERROR_SEQUENCE      = 0x05
RCI_ANNOUNCE_COMPR      = 0xB0
RCI_COMPR_NONE          = 0x00
RCI_COMPR_ZLIB          = 0x01    # Not actually specified as yet


class EDP:
    """Connection info."""

    # state information
    EDP_STATE_CLOSED      = 0    # Closed, ready to open
    #EDP_STATE_RESOLVING   = 1    # Initial DNS resolve
    EDP_STATE_OPENING     = 2    # Opening transport
    EDP_STATE_SECURING    = 3    # Securing transport
    EDP_STATE_UNSECURING  = 4    # Unsecuring transport
    EDP_STATE_CLOSING     = 5    # Closing transport
    EDP_STATE_REDIR_CLS   = 6    # Closing prior to redirect
    EDP_STATE_REDIRECTING = 7    # Closed, opening aain with redirected URI
    EDP_STATE_REBOOT      = 8    # Reboot requested (edp_close() called with -1)    
    # Following 2 states alternate when transport connection established.
    EDP_STATE_OPEN        = 10   # Open, sent initial MT version message. In this state, keepalives are active, and facility callbacks may be invoked.
    EDP_STATE_MSGHDR      = 11   # Received initial type/length field for next received message at lowest layer.    
    
    # Higher state protocol
    PHASE_INIT         = 0   # Received MT version OK, send inner versioning
    PHASE_WAIT_VERS_OK = 1   # Waiting for inner version OK
    PHASE_SECURING     = 2   # Received inner version OK, securing
    PHASE_DISCOVERY    = 8
    PHASE_FACILITY     = 10    
    
    # RCI State
    RCI_STATE_READY    = 0   # Initial state, ready to get server data
    RCI_STATE_RX       = 1   # Reading server data
    RCI_STATE_RXDONE   = 2   # Server sent disconnect mesage
    RCI_STATE_ERROR    = 10  # Encountered error    
    
    
    def __init__(self, rci_process_request=None, device_id=None, host=None, port=None, device_name=None):
        self.sock = None
        "TCP socket"
        self.state = self.EDP_STATE_CLOSED
        "Current low-level state"
        self.phase = self.PHASE_INIT
        "Higher level protocol phase"
        self.hostname = host or settings['idigi_server']
        "Host name"
        self.uri = "en://" + self.hostname
        "original URI"
        self.red_uri = None
        "Redirected URI (or None for first try)"
        self.port = port or settings['idigi_port']
        "Host port (usually 3197)"
        self.device_id = device_id or settings['device_id']
        "Device ID (shows up on iDigi)"
        self.device_name = device_name or settings['device_name']
        "Device Name for iDigi connection"
        self.fac = {}
        "Facility handlers - {facility_id: function pointer}"
        self.rx_intvl = 0
        "Timeout interval (ms) for foll."
        self.rx_ka = 0
        """RX keepalive timer - use this to send KAs to 
        server if no messages sent in the interval."""
        self.tx_intvl = 0
        "Timeout interval (ms) for foll."
        self.tx_ka = 0
        """TX keepalive timer.  This is set to 
        WAIT * TX in the initial negotiation. 
        If no KAs received from server in this
        interval, close the connection."""
        self.msg_type = 0
        "Received message type"
        self.msg_len = 0
        "Length of the current message"
        self.rxdata = ""
        "Buffer to read in current message."
        self.epoch = 0
        "Session start time (time.clock())"
        self.rci_state = self.RCI_STATE_READY
        "RCI State information for receiving RCI commands"
        self.rci_len = 0
        "Total length of RCI message"
        self.rci_rxdata = ""
        "Buffer to store incoming RCI messages"
        self.rci_process_request = rci_process_request
        "Function pointer to handle RCI requests"
    
    def run_forever(self):
        while(1):
            self.tick()
            time.sleep(0.1)
    
    def close(self, nicely):
        self.rx_data = ""
        self.sock.close()
        if nicely > 0 and (self.state == self.EDP_STATE_OPEN or self.state == self.EDP_STATE_MSGHDR):
            if nicely == 2:
                self.state = self.EDP_STATE_REDIR_CLS
            else:
                self.state = self.EDP_STATE_CLOSING
            return
        if self.state == self.EDP_STATE_OPENING:
            pass#self.sock.close() # TODO: abort exist?
        if nicely < 0:
            self.state = self.EDP_STATE_REBOOT
        else:
            self.state = self.EDP_STATE_CLOSED

    def send_msg(self, msg_type, msg):
        wlist = select.select([], [self.sock], [], 0)[1]
        if not wlist:
            self._handle_error("Socket not writable")
            return -EIO
        logging.info("EDP: %s -->: sending message type=0x%04X totlen=%u" % (self._get_elapsed(), msg_type, len(msg)))
        logging.debug("EDP: %s" % str(["%02X" % ord(x) for x in msg]) + "\t" + msg)

        self.sock.send(struct.pack("!HH", msg_type, len(msg)) + msg)
        self.rx_ka = time.clock() + self.rx_intvl
        return 0

    def send_fac(self, fac, msg):
        """This is like edp_send_msg, except it assumes EDP_PAYLOAD and
        0x0000 for the security layer flags (i.e. no encryption and
        normal payload data).  fac is the facility code (in reversed order
        i.e. use the EDP_FACILITY_* macro values)."""
        wlist = select.select([], [self.sock], [], 0)[1]
        if not wlist:
            self._handle_error("Socket not writable")
            return -EIO
                    
        logging.info("EDP: %s -->: sending facility message fac=0x%04X len=%u" % (self._get_elapsed(), fac, len(msg)))
        logging.debug("EDP: %s" % str(["%02X" % ord(x) for x in msg]) + "\t" + msg)
        
        self.sock.send(struct.pack("!HHHH", EDP_PAYLOAD, len(msg)+4, 0, fac) + msg)
        self.rx_ka = time.clock() + self.rx_intvl
        return 0


    def tick(self):
        """Pass non-None URI to start, None uri to continue, until returns other 
        than -EAGAIN.  Returns 0 if no URI in state CLOSED (meaning state is
        ready to re-open with new URI)."""
        try:
            if self.state == self.EDP_STATE_REDIRECTING:
                logging.info("EDP: Redirecting to %ls" % self.red_uri)
                self.uri = self.red_uri
                self.phase = self.PHASE_INIT
                self.state = self.EDP_STATE_OPENING
    
            
            elif self.state == self.EDP_STATE_REBOOT:
                return -ENETRESET
            
            
            elif self.state == self.EDP_STATE_CLOSED:
                self.rxdata = ""
                self.epoch = time.clock()
                self.uri = "en://" + self.hostname # TODO: do this nicely...
                self.red_uri = None
                self.phase = self.PHASE_INIT
                self.state = self.EDP_STATE_OPENING
            
            
            elif self.state == self.EDP_STATE_OPENING:
                try:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.connect((self.hostname, self.port))
                except Exception, e:
                    logging.error("EDP: Error opening socket: %s" % e)
                    return #TODO: error?
                
                logging.info("EDP: Socket connected!")
    
                self.epoch = time.clock()
                self.state = self.EDP_STATE_OPEN
                
                logging.info("EDP: My device ID is: %s" % str(self.device_id))
                
                try:
                    settings['my_ipaddress'] = self.sock.getsockname()[0]
                    logging.info("EDP: my IP is %s" % settings['my_ipaddress'])
                except Exception, e:
                    logging.error("EDP: error calling getsockname(): %s" % e)
                
                # Write the version mesage (Version 2 of MT),
                # RX interval (16 sec), TX interval (16 sec) and Wait (3).
                # This won't block, since have empty tx buffer.
                # Also can't fail.
                payload = "\x00\x04\x00\x04\x00\x00\x00\x02" 
                payload += "\x00\x20\x00\x02"
                payload += struct.pack("!H", EDP_KEEPALIVE_INTERVAL)
                payload += "\x00\x21\x00\x02"
                payload += struct.pack("!H", EDP_KEEPALIVE_INTERVAL)
                payload += "\x00\x22\x00\x02"
                payload += struct.pack("!H", EDP_KEEPALIVE_WAIT)
                self.sock.send(payload)
    
                self.rx_intvl = EDP_KEEPALIVE_INTERVAL
                self.tx_intvl = EDP_KEEPALIVE_INTERVAL * EDP_KEEPALIVE_WAIT
                self.rx_ka = time.clock() + self.rx_intvl
                self.tx_ka = time.clock() + self.tx_intvl
                
    
            elif self.state == self.EDP_STATE_MSGHDR or self.state == self.EDP_STATE_OPEN:
                if time.clock() > self.tx_ka:
                    # Server died
                    self._handle_error("Server Died")
                    return -ETIMEDOUT
    
                if time.clock() > self.rx_ka:
                    # Send keepalive msg
                    rc = self.send_msg(EDP_KEEPALIVE, "")
                    if rc:
                        return rc
    
                # read data from socket buffer
                rlist = select.select([self.sock], [], [], 0)[0]
                if rlist:
                    #self._handle_error("Socket not readable") #TODO: should this be a real error?
                    #return -EIO
                    self.rxdata += self.sock.recv(4096)               
                
                # Check if complete message ready and, if so, send it to
                # next protocol layer.
                if self.state == self.EDP_STATE_OPEN:
                    if len(self.rxdata) >= 4:
                        # OK, got header (type+length)
                        self.msg_type, self.msg_len = struct.unpack("!hh", self.rxdata[0:4])
                        self.state = self.EDP_STATE_MSGHDR
                    else:
                        return -EAGAIN
    
                # OK, must be in state self.EDP_STATE_MSGHDR.  Get complete message
                if len(self.rxdata) >= self.msg_len + 4:
                    self.handle_msg(self.rxdata[4:self.msg_len + 4])
                    # clear message from buffer
                    self.rxdata = self.rxdata[self.msg_len + 4:]
                    if self.state == self.EDP_STATE_MSGHDR:
                        # Done with this msg, continue.  Otherwise, may have closed for redirect etc.
                        self.state = self.EDP_STATE_OPEN                     
                
            elif self.state == self.EDP_STATE_REDIR_CLS:
                #if socket not alive 
                self.state = self.EDP_STATE_REDIRECTING
                
            elif self.state == self.EDP_STATE_CLOSING:
                #if socket not alive 
                self.state = self.EDP_STATE_CLOSED
                return 0
            
            else:
                # Bad state to be calling this
                return -EINVAL
        except Exception, e:
            if self.sock:
                self.sock.close()
            self.rxdata = ""
            self.state = self.EDP_STATE_CLOSED
            logging.error("EDP: tick Exception: %s" % e)
            time.sleep(RECONNECT_TIME) # give a few seconds before trying to reconnect...
        return -EAGAIN
            
    
    def handle_msg(self, msg):
        """self.msg_type is current message type, msg contains the message."""        
        # reset server KA timer
        self.tx_ka = time.clock() + self.tx_intvl

        if self.msg_type != EDP_KEEPALIVE:
            logging.info("EDP: %s <-- : got message type=0x%04X len=%u" % (self._get_elapsed(), self.msg_type, len(msg)))
            logging.debug("EDP: %s" % str(["%02X" % ord(x) for x in msg]) + "\t" + msg)

        if self.msg_type == EDP_PAYLOAD:
            if self.phase == self.PHASE_WAIT_VERS_OK:
                
                if len(msg) != 1 or ord(msg[0]):
                    logging.error("EDP: bad version - code %d (msg len %d) waiting for inner vers OK" % (ord(msg[0]), len(msg)))
                    self._handle_error("Bad version")
                else:
                    # Success, proceed to security
                    self.phase = self.PHASE_SECURING
                    
                    # We're using simple identification here...
                    self.send_msg(EDP_PAYLOAD, "\x80\x00")
                    payload = "\x81" # Device ID
                    payload += self._device_id_str()
                    self.send_msg(EDP_PAYLOAD, payload)

                    # Connection URI
                    if self.red_uri is not None:
                        conn_uri = self.red_uri
                    else:
                        conn_uri = self.uri
                    payload = struct.pack("!BH", 0x86, len(conn_uri))
                    payload += conn_uri
                    self.send_msg(EDP_PAYLOAD, payload)
                    

                    # Simple form does not require waiting for any response,
                    # so proceed to discovery...
                    self.phase = self.PHASE_DISCOVERY
                    payload = "\x00" # Security layer payload
                    payload += "\x04" # Device type discovery message
                    payload += struct.pack("!H", len(self.device_name))
                    payload += self.device_name
                    self.send_msg(EDP_PAYLOAD, payload)

                    # Initialization: send a few odd messages
                    if self.red_uri is not None:
                        payload = "\x04\x01\x0DRedirected OK" # Redirected OK
                        payload += struct.pack("!H", len(self.uri))
                        payload += self.uri
                        self.send_fac(EDP_FACILITY_CONN_CONTROL, payload)
                    else:
                        payload = "\x04\x00\x00\x00\x00" # Not redirected
                        self.send_fac(EDP_FACILITY_CONN_CONTROL, payload)

                    # Connection report
                    payload = "\x05\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF"
                    # append IP
                    IP_list = [int(num) for num in socket.gethostbyname(socket.gethostname()).split(".")]
                    payload += struct.pack("!BBBBB", IP_list[0], IP_list[1], IP_list[2], IP_list[3], 0x01)
                    payload += settings['MAC'] # 6 bytes 
                    self.send_fac(EDP_FACILITY_CONN_CONTROL, payload)
                    
                    # Announce RCI compression.
                    #self.send_fac(EDP_FACILITY_RCI, "\xB0\x01\x01\xFF") #ZLIB, reply
                    self.send_fac(EDP_FACILITY_RCI, "\xB0\x00\x00") # None, no reply

                    # Done init
                    self.send_msg(EDP_PAYLOAD, "\x00\x05")
                    self.phase = self.PHASE_FACILITY
            
            
            elif self.phase == self.PHASE_SECURING:
                pass    
            elif self.phase == self.PHASE_DISCOVERY:
                pass    
            elif self.phase == self.PHASE_FACILITY: 
                if len(msg) < 5:
                    logging.error("EDP: bad message length %u" % len(msg))
                    self._handle_error()
                
                fac = struct.unpack("!H", msg[2:4])[0]
                if fac == EDP_FACILITY_CLIENT_LOOPBACK:
                    self.send_msg(EDP_PAYLOAD, msg)
                elif fac == EDP_FACILITY_CONN_CONTROL:
                    opcode = ord(msg[4])
                    if opcode == 0x00: # disconnect (server has nothing to send)
                        logging.warning("EDP: got disconnect request - ignoring for now")
                        # We should theoretically close, but server seems to
                        # send this even though we have successfully started
                        # and should not close.  Just ignore it for now, until
                        # situation is clarified.
                        #self.close(1)
                        #time.sleep(RECONNECT_TIME) # give a few seconds before trying to reconnect...
                    elif opcode == 0x03: # redirect
                        # Ignore the URL count.  Just use the 1st URL, since
                        # we have a nameserver.
                        urllen = struct.unpack("!H", msg[6:8])[0]                
                        if len(msg) < 13 or ord(msg[5]) < 1 or urllen+8 > len(msg):
                            logging.error("EDP: Redirect error - no URL provided, or bad URL length")
                            self._handle_error("Redirect Error")
                        else:
                            self.red_uri = msg[8:8+urllen]
                            self.close(2) #close and redirect
                elif fac == EDP_FACILITY_RCI:
                    self.handle_rci(msg[4:])
                else:
                    handler = self.fac.get(fac)
                    if handler is None:
                        logging.error("EDP: got unhandled facility code 0x%04X" % fac)
                    else:
                        handler(msg[4:])
                
        elif self.msg_type == EDP_VERSION_OK:
            if self.phase == self.PHASE_INIT:
                #Send inner versioning info
                self.send_msg(EDP_PAYLOAD, "\x00\x00\x01\x20")
                self.phase = self.PHASE_WAIT_VERS_OK
        elif self.msg_type == EDP_VERSION_BAD:
            logging.error("EDP: server error - bad version")
            self._handle_error()            
        elif self.msg_type == EDP_SERVER_OVERLOAD:
            logging.warning("EDP: server error - overloaded")
            self._handle_error()
        else:
            # Ignore anything unknown.  (This also handles keepalives)
            if self.msg_type != EDP_KEEPALIVE:
                logging.info("EDP: unexpected message type 0x%04X" % self.msg_type)

        return 0

    def rci_send_error(self, code):
        payload = struct.pack("!BB", RCI_ERROR_DETECTED, code)
        self.edp_send_fac(EDP_FACILITY_RCI, payload)
        self.rci_state = self.RCI_STATE_ERROR        

    def handle_rci(self, rci_msg):
        logging.info("EDP: Received RCI message")
        opcode = ord(rci_msg[0])
        
        if opcode == RCI_COMMAND_REQ_START:
            if self.rci_state != self.RCI_STATE_READY:
                self.rci_send_error(RCI_ERROR_SEQUENCE)
                return    
            compression, self.rci_len = struct.unpack("!BI", rci_msg[1:6])
            if compression: 
                # can't handle compression
                self.rci_send_error(RCI_ERROR_FATAL)
                return
            self.rci_rxdata += rci_msg[6:]
            self.rci_state = self.RCI_STATE_RX
            
        elif opcode == RCI_COMMAND_REQ_DATA or opcode == RCI_COMMAND_REQ_END:
            if self.rci_state != self.RCI_STATE_RX:
                # Forgive zero length stuff.  He might have provided everything
                # in a REQ_DATA (which we processed) and then sent an empty END.
                if not len:
                    return
                self.rci_send_error(RCI_ERROR_SEQUENCE)
            else:
                self.rci_rxdata += rci_msg[1:]
        elif opcode == RCI_ERROR_DETECTED:
            logging.error("EDP: RCI got error code 0x%02X\n" % rci_msg[1])
            self.rci_state = self.RCI_STATE_ERROR
            self.edp_close(0)
        else:
            #Ignore anything else (for upward compat) - could be
            # server ACKs, announce compression etc.
            return
        
        if self.rci_len == len(self.rci_rxdata) or opcode == RCI_COMMAND_REQ_END:
            response = self.rci_process_request(self.rci_rxdata)
            self.rci_rxdata = ""
            self.rci_len = 0
            self.rci_state = self.RCI_STATE_READY
            header = struct.pack("!BBI", RCI_COMMAND_REPLY_START, 0, len(response))
            self.send_fac(EDP_FACILITY_RCI, header + response)


    def _handle_error(self, errmsg = ""):
        logging.error("%s - EDP: unexpected error:%s , aborting connection" % (self._get_elapsed(), errmsg))
        self.close(0)

    def _get_elapsed(self):
        return "%8.2f" % (time.clock() - self.epoch)
    
    def _device_id_str(self):
        hex_str = ""
        device_str = ""
        for ch in self.device_id:
            if ch in string.hexdigits:
                hex_str += ch
        while len(hex_str):
            device_str = struct.pack("!I", int(hex_str[-8:], 16)) + device_str
            hex_str = hex_str[:-8]
        return device_str

if __name__ == '__main__':
    edp = EDP()
    edp.run_forever()
