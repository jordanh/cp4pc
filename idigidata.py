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

#send_to_idigi (data, filename, [collection, content_type, archive=False, append=False, timeout]) -> (success, error, errmsg)
#
#Send data to the iDigi data service and wait for the response.
#_data_ is the string or binary data to send.
#_filename_ is the server filename to store data.
#Optional _collection_ is the subcollection where the file should be stored.
#Optional _content_type_ is the MIME type of the data.
#Optional _archive_ is True to archive the data.
#Optional _append_ is True to append the data to an existing resource.
#Optional _timeout_ is maximum time in seconds to wait for a response.
#
#Returns (success, error, errmsg) if successful; raises an Exception on error.
#_success_ is True if the data was stored sucessfully.
#_error_ is the status code of the transfer.
#_errmsg_ is the status message of the transfer.

import cwm
import httplib

#NOTE: only data and filename do anything currently
def send_to_idigi(data, filename, collection = None, content_type = None, archive = False, append = False, timeout = None):
    host, token, path, port, securePort = cwm._get_ws_parms()
    
    webservice = httplib.HTTP(host, port)
    webservice.putrequest("PUT", "%s/%s" % (path, filename))
    webservice.putheader("Authorization", "Basic %s" % token)
    webservice.putheader("Content-type", "text/xml; charset=\"UTF-8\"")
    webservice.putheader("Content-length", "%d" % len(data))
    webservice.endheaders()
    webservice.send(data)
    
    # get the response
    statuscode, statusmessage, header = webservice.getreply()
    webservice.close()
    if statuscode != 200 and statuscode != 201:
        success = False
    else:
        success = True
    return success, statuscode, statusmessage
