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
"""Filler for compiling cwm_data.py"""

from simulator_settings import settings

def _get_ws_parms():
    host = settings["idigi_server"]
    device = settings["device_id"]
    # find a better place for this
    token = 'cwm_ds'
    path =  '/ws/device'
    port = 80
    device = device.replace('-', '')
    device = device.lower()
    token = "0x" + device + ":" + token
    # NDS code says uu encode, but its really the base64 variant
    encoded = token.encode('base64_codec')
    encoded = encoded.strip()
    address = host #+ ":" + str(port)

    return address, encoded, path, port, 0x1337

