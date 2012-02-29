# Copyright (c) 2009-2012 Digi International Inc., All Rights Reserved
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

__version__ = "1.6.0"

# this file stores the settings from the command line arguments.

settings = {}
# example and defaulted Settings

# serial port settings for XBee
#settings['com_port'] = 'COM11'
settings['baud'] = 115200

# iDigi Settings
#settings['device_id'] = "00000000-00000000-DEAD01FF-FF00BEEF"
settings['idigi_server'] = 'developer.idigi.com'
settings['idigi_port'] = 3197
settings['local_port'] = 8080
settings['device_name'] = 'PC Gateway'

# Settings from computer
#TODO: get these from the local computer
settings['MAC'] = '\x00\x0F\xFE\x87\x46\x91'
