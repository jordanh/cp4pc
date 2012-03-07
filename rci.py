# Copyright (c) 2009 Digi International Inc., All Rights Reserved
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

"Simulation of rci module on ConnectPort"

import thread
import time
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
try:
   from xml.etree import ElementTree
except:
   import ElementTree

from lock_dict import lockDict
from query_state import query_state
from query_setting import query_setting
from simulator_settings import settings
import cStringIO
import logging

__all__ = ['add_rci_callback', 'process_request', 'stop_rci_callback']

# set up logger
logger = logging.getLogger("RCI")
stderr_handler = logging.StreamHandler()
stderr_formatter = logging.Formatter("[%(asctime)s] %(levelname)s RCI: %(message)s", "%a %b %d %H:%M:%S %Y")
stderr_handler.setFormatter(stderr_formatter)
logger.addHandler(stderr_handler)
logger.setLevel(logging.INFO) #TODO: set this based on simulator settings!


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
    
    #check parameters
    if not callable(callback):
        raise TypeError("2nd parameter must be a function")
    if name in rci_callbacks:
        raise ValueError("unknown error")
    
    rci_callbacks[name] = callback
    while(1):
        if name not in rci_callbacks:
            return
        time.sleep(1)
    
def process_request(request):
    """ 
    process_request(request) -> response
    
    Process an RCI request and returns 
    the response.
    """
    rci_response = ""
    
    try:
        XML_tree = ElementTree.parse(cStringIO.StringIO(request))
    except Exception, e:
        logger.error("failed to parse %s (%s)" % (request, e))
        # improper XML, return error response
        #TODO: create proper response
        return "<error>XML parsing failed</error>"

    rci_request = XML_tree.getroot()
    if rci_request.tag.strip() != "rci_request":
        logger.error("rci_request tag missing in %s" % request)
        return _wrap_rci_response("<error>XML missing rci_request tag</error>")
    for child in list(rci_request):
        command = child.tag.strip()
        if command == "do_command":
            # get target string
            target_string = child.get("target")
            if target_string is None:
                logger.warning("do_command missing target")
                rci_response += "<do_command><error>RCI missing target</error></do_command>"
                continue
            # make sure target string registered
            callback = rci_callbacks.get(target_string)
            if callback is None:
                logger.warning("do_command('%s'): name not registered" % target_string)
                rci_response += """<do_command><error id="2"><hint>%s</hint><desc>Name not registered</desc></error></do_command>""" % target_string
                continue
            logger.info("processing do_command('%s')" % target_string)
            # get payload for do_command                
            xml_payload = ""
            for parameter in list(child):
                xml_payload += ElementTree.tostring(parameter)
            # call callback and append to response XML
            try:
                rci_response += "<do_command target=\"%s\">" % (target_string)
                rci_response += callback(xml_payload) + "</do_command>"
            except Exception, e:
                logger.error("do_command(%s) exception (%s)" % (command, e))
                rci_response += """<do_command><error>Exception while processing do_command</error></do_command>""" # TODO: get correct error
        elif command == "query_setting":
            logger.info("processing %s" % command)
            rci_response = query_setting()
        elif command == "query_state":
            logger.info("processing %s" % command)
            rci_response = query_state()
        else:
            logger.warning("no handler for %s" % command)
    return _wrap_rci_response(rci_response)
    
def _wrap_rci_response(xml):
    return """<rci_reply version="1.1">""" + xml + """</rci_reply>"""    

def stop_rci_callback(name):
    """ 
    stop_rci_callback(name) -> None
    
    Stops the previously called add_rci_callback
    with the specified name.
    """
    del rci_callbacks[name]
    
class RCIHandler(BaseHTTPRequestHandler):
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

def start_server(local_port = 80):
    logger.info("Starting web server on port %u..." % local_port)
    server = HTTPServer(("", local_port), RCIHandler)
    server.serve_forever()


#NOTE: code will only on first import - Python only imports files once
# start HTTP server thread for processing RCI requests
local_port = settings.get("local_port", 0)
if local_port:
    thread.start_new_thread(start_server, (local_port,))

rci_callbacks = lockDict()

import edp
edp_obj = edp.EDP(process_request)
thread.start_new_thread(edp_obj.run_forever, ())

import addp
addp_obj = addp.ADDP()
thread.start_new_thread(addp_obj.run_forever, ())
