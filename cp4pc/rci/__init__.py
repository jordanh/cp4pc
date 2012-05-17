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
import sys
import logging
import thread
import threading
import time
from wsgiref.simple_server import make_server, WSGIRequestHandler
import webob
from webob.dec import wsgify

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

# filesystem target
from controller.filesystem import FileSystemTarget
# ZigBee handlers - initialized at bottom of file
from controller.zigbee import ZigbeeTarget

import xbee
import edp
import addp

from simulator_settings import settings


__all__ = ['add_rci_callback', 'process_request', 'stop_rci_callback', #standard Digi functions 
           'set_wsgi_handler', 'connected'] # extra functions for running on a PC

# set up logger
logger = logging.getLogger("cp4pc.rci")
logger.setLevel(logging.INFO)

class RCIWSGIRequestHandler(WSGIRequestHandler):
    # overridden from WSGIRequestHandler::BaseHTTPRequestHandler
    def log_message(self, format, *args):
        global logger
        logger.debug("%s - - [%s] %s" %
                         (self.address_string(),
                          self.log_date_time_string(),
                          format%args))

class RCIHandler(object):
    """Manage the device tree and its mapping to rci requests"""

    def __init__(self, device_tree):
        self.device_tree = device_tree

    def _rci_response(self, body):
        return "<rci_reply version=\"1.1\">%s</rci_reply>" % body

    def add_callback(self, name, callback):
        do_command = self.device_tree.get('do_command')
        if do_command is None:
            raise Exception("do_command not supported")
        else:
            global logger
            logger.info("do_command target '%s' registered" % name)
            return do_command.add_callback(name, callback)
            
    def remove_callback(self, name):
        do_command = self.device_tree.get('do_command')
        if do_command:
            return do_command.remove_callback(name) 

    def handle_rci_request(self, xml_text):
        """Return RCI response based on our tree structure"""
        global logger
        root = ET.fromstring(xml_text)

        return_xml = ""
        if not root.tag == "rci_request":
            logger.warn("RCIHandler received non-RCI request with root tag %s" % root.tag)
            return_xml = ('<error id="1" desc="Expected rci_request root'
                          ' node but got something else />')
        for xml_child in root:
            logger.info("Received %s request" % xml_child.tag)
            logger.debug("Full request %s"%xml_text)
            for device_node in self.device_tree:
                if device_node.name == xml_child.tag:
                    node_xml = device_node.handle_xml(xml_child)
                    break
            else:
                logger.warning("Unsupported tag %s"%xml_child.tag)
                node_xml = ('<{tag}><error id="1" '
                            'desc="Unknown tag" /></{tag}>'
                               .format(tag=xml_child.tag))
            return_xml += node_xml

        return_xml = self._rci_response(return_xml)
        logger.debug("Full response %s" % return_xml)

        return return_xml

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

def set_wsgi_handler(handler):
    global http_server
    http_server.set_handler(handler)

def connected():
    global edp_client
    return edp_client.state in [edp.EDP.EDP_STATE_OPEN, edp.EDP.EDP_STATE_MSGHDR]

#===============================================================================
# Helper classes and functions
#===============================================================================

class HTTPHandler(threading.Thread):
    def __init__(self, handler = None):
        threading.Thread.__init__(self)
        threading.Thread.setDaemon(self,True)
        self.handler = handler # will process other HTTP requests
    
    def run(self):
        while(1):
            #NOTE: we take no action if the local port is changed dynamically
            local_port = settings.get('local_port')
            if not local_port:
                time.sleep(1)
                continue
            logger.info("Starting web server at http://localhost:%d" % local_port)
            make_server('', local_port, self, handler_class=RCIWSGIRequestHandler).serve_forever()
    
    def set_handler(self, handler):
        self.handler = handler
    
    def handle_request(self, request):
        if request.method == "POST":
            return webob.Response(process_request(request.body), content_type='application/xml')
        else:
            return webob.exc.HTTPMethodNotAllowed()    
    
    @wsgify
    def __call__(self, request):
        if request.path == '/UE/rci':
            #handle request
            return self.handle_request(request)
        elif self.handler:
            # pass on to handler
            return self.handler(request)
        else:
            # request not handled
            return webob.exc.HTTPNotFound()

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
http_server = HTTPHandler()
http_server.start()

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
    .attach(BranchNode('boot_stats', 'Primary interface')
        .attach(SimpleLeafNode('ip', dtype=DTYPE.IPV4, desc='IP Address', accessor=create_accessor('ip_address', '0.0.0.0')))
    )
    .attach(BranchNode('zigbee_state', 'Gateway XBee')
        .attach(SimpleLeafNode('gateway_addr', dtype=DTYPE.XBEE_EXT_ADDR, desc='XBee extended address', accessor=lambda: ':'.join("%02x" % ord(x) for x in xbee.ddo_get_param(None, 'SH')+xbee.ddo_get_param(None, 'SL'))))
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
    .attach(ZigbeeTarget())
)

rci_handler = RCIHandler(rci_tree)
# Create EDP object - will connect to iDigi and has a callback for RCI requests
edp_client = edp.EDP(rci_process_request=process_request)
thread.start_new_thread(edp_client.run_forever, ())
