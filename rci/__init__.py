import sys
import logging
import thread
import time
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
try:
    from xml.etree import cElementTree as ET
except:
    try:
        from xml.etree import ElementTree as ET
    except:
        import ElementTree as ET

from model.base import BranchNode, LeafNode, SimpleLeafNode, DTYPE
from model.device import DeviceRoot, RciDescriptor, RciState, RciSettings, RciDoCommand

# Handlers
from controller.rcihandler import RCIHandler 
# filesystem target
from controller.filesystem import FileSystemTarget
# ZigBee handlers - initialized at bottom of file

import edp
import addp

from simulator_settings import settings


__all__ = ['add_rci_callback', 'process_request', 'stop_rci_callback']

# set up logger
logger = logging.getLogger("RCI")
stderr_handler = logging.StreamHandler()
stderr_formatter = logging.Formatter("[%(asctime)s] %(levelname)s RCI: %(message)s", "%a %b %d %H:%M:%S %Y")
stderr_handler.setFormatter(stderr_formatter)
logger.addHandler(stderr_handler)
logger.setLevel(logging.INFO)

rci_callback_names = [] #TODO: find a better way to do this?  Seems like a real waste.
def add_rci_callback(name, callback):
    """
    add_rci_callback(name, callback) -> None

    Function callback is called when name is sent
    as a rci do_command target.

    callback will be called with a string representing
    the xml contained within the do_command.  callback
    returns a string which will be returned to the caller
    as the result of the request.  The returned string must
    be valid xml.  Returning invalid xml will result in
    invalid xml being returned to the requester.  Note, plain
    text is valid xml.  Binary data must be base64 encoded.
    If no reply is expected, an empty string ("") must be
    returned.
    
    This is a blocking call.  callback will be called from
    the thread that calls this function.
    
    There are no limitations on what the callback function does,
    However, device processing waits for a response so it is
    recommended to keep processing to a minimum.  Best practice is
    to respond immediately and then perform processing in another
    thread.  If no response is returned from callback within 45
    seconds, the device will stop waiting and return a warning to
    the RCI requester.
    """
    global rci_handler
    global rci_callback_names
    #check parameters
    if not callable(callback):
        raise TypeError("2nd parameter must be a function")
    if name in rci_callback_names:
        raise ValueError("name already registered: %s" % name)
    rci_handler.add_callback(name, callback)

    rci_callback_names.append(name)
    while(1):
        # check to see if rci callback has been stopped
        if name not in rci_callback_names:
            return
        time.sleep(0.5)

def stop_rci_callback(name):
    """ 
    stop_rci_callback(name) -> None
    
    Stops the previously called add_rci_callback
    with the specified name.
    """
    global rci_handler
    rci_handler.remove_callback(name)
    if name in rci_callback_names:
        rci_callback_names.remove(name)
    
def process_request(request):
    """ 
    process_request(request) -> response
    
    Process an RCI request and returns 
    the response.
    """
    global rci_handler
    return rci_handler.handle_rci_request(request)


class RCI_HTTPHandler(BaseHTTPRequestHandler):
    #TODO: Could add get handler to support a locally hosted webpage
    def do_POST(self):
        try:
            if self.path != "/UE/rci":
                self.send_response(404) #incorrect address
                return
            xml = self.rfile._rbuf # Hack, but don't know a better way to read data...
            response = process_request(xml)
            self.wfile.write(response)
        except:
                self.send_response(400) #bad request

def start_rci_server(local_port = 80):
    logger.info("Starting web server on port %u..." % local_port)
    server = HTTPServer(("", local_port), RCIHandler)
    server.serve_forever()

def create_accessor(name, default=''):
    return lambda: str(settings.get(name, default)) #make sure return value is string

#===============================================================================
# Create EDP, ADDP, and RCI objects
#===============================================================================

# Create ADDP object - will handle ADDP requests
# NOTE: this is mostly independent of the RCI module
addp_server = addp.ADDP()
addp_server.start()

#NOTE: code will only run on first import - Python only imports files once
# start HTTP server thread for processing RCI requests
local_port = settings.get("local_port", 0)
if local_port:
    thread.start_new_thread(start_rci_server, (local_port,))

# Create RCI tree that responds to RCI requests
rci_tree = DeviceRoot()
#-- RCI Descriptor --#
rci_tree.attach(RciDescriptor(rci_tree))
#-- RCI STATE --#
rci_tree.attach(RciState()
    .attach(BranchNode('device_info', 'Device Information')
        .attach(SimpleLeafNode('mac', dtype=DTYPE.MAC_ADDR,
                                desc="MAC Address",
                                accessor=lambda: ":".join("%02X" % ((settings.get('mac', 0) >> (i*8)) & 0xFF) for i in xrange(6))))
        .attach(SimpleLeafNode('product', dtype=DTYPE.STRING,
                                desc="product",
                                accessor=create_accessor('device_type')))
        .attach(SimpleLeafNode('company', dtype=DTYPE.STRING,
                               desc="company",
                               accessor=create_accessor('company')))
        .attach(SimpleLeafNode('os_name', dtype=DTYPE.STRING,
                               desc="Name of host operating system",
                               accessor=lambda: sys.platform))
    )
)
#-- RCI Settings --#
rci_tree.attach(RciSettings()
    .attach(BranchNode("system", 'System Settings')
        .attach(SimpleLeafNode("contact", accessor=create_accessor('contact')))
        .attach(SimpleLeafNode("location", accessor=create_accessor('location')))
        .attach(SimpleLeafNode("description", accessor=create_accessor('description')))
    )
    .attach(BranchNode("mgmtglobal", 'Global Mangement')
        .attach(SimpleLeafNode("deviceid", accessor=create_accessor('device_id')))
    )
)

#-- RCI Reboot --#
#rci_tree.attach(RciReboot())

#-- RCI do_command --#
rci_tree.attach(RciDoCommand()
    .attach(FileSystemTarget())
#    .attach(ZigbeeTarget())
)

rci_handler = RCIHandler(rci_tree)
# Create EDP object - will connect to iDigi and has a callback for RCI requests
edp_client = edp.EDP(device_id=settings['device_id'], 
                     device_type=settings['device_type'], 
                     host=settings['idigi_server'], 
                     mac=settings['mac'], 
                     rci_process_request=process_request, 
                     vendor_id=settings.get('vendor_id', None), 
                     idigi_certs_file=settings.get('idigi_certs_file', ''))
thread.start_new_thread(edp_client.run_forever, ())
