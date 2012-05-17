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
"""PC version of digicli.  Doesn't not actually process requests, but provides dummy functions"""

def digicli(in_str):
    """digicli(str) --> (status, [output_string_list])
    Over here.'"""
    
    in_str = in_str.strip()
    if in_str == 'info device' or in_str == "info dev":
        # only used for memory statistics in SE_Framework.
        return (True, [
"Device Information:",
"",
"Product              : ConnectPort X2",
"MAC Address          : 00:40:9D:00:00:00",
"Firmware Version     : 2.13.0.9 (Version 82002458_B_SA9 04/21/2011)",
"Boot Version         : 1.1.2 (release_82001228_A)",
"Post Version         : 1.1.3 (release_82002307_C)",
"Product VPD Version  : release_82002309_B",
"Product ID           : 0x0056",
"Hardware Strapping   : 0x07BF",
"CPU Utilization      : 54 %",
"Uptime               : 4 minutes, 4 seconds",
"Current Date/Time    : Tue May 17 22:13:17 2011",
"Total Memory         : 8388608",
"Used Memory          : 7467556",
"Free Memory          : 921052"])
    elif in_str == 'boot action=reset':
        #from sys import exit
        #exit()
        return (True, [""])
    return (False, ["Fake process digicli: %s" % in_str])
