# Copyright (c) 2009-2010 Digi International Inc., All Rights Reserved
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


import time
from simulator_settings import settings

time.clock() # initialize for uptime

# Zigbee State capability 0x200 required for Digi X-Grid/Open EMS 
def query_state():
    try:
        # FIXME: this should be the EUI, not device ID.
        eui = settings['device_id'].replace("-", "")
        eui = eui[-16:]
        eui = "%s:%s:%s:%s:%s:%s:%s:%s" % (eui[:2],eui[2:4],eui[4:6],eui[6:8],eui[8:10],eui[10:12], eui[12:14],eui[14:16])
        retval = """
            <query_state>
              <device_info>
                <mac>00:00:00:00:00:00</mac>
                <product>PC Simulator</product>
                <company>Digi International</company>
                <boot>99999000</boot>
                <post>99999001</post>
                <firmware>99999002</firmware>
              </device_info>
              <device_stats>
                <uptime>%d</uptime>
                <freemem>1000000000</freemem>
              </device_stats>
              <boot_stats>
                <eth_speed>auto</eth_speed>
                <eth_duplex>auto</eth_duplex>
                <dhcp>on</dhcp>
                <ip>%s</ip>
                <subnet>255.255.255.0</subnet>
                <gateway>10.40.18.1</gateway>
                <autoip>on</autoip>
                <addp>off</addp>
                <static>on</static>
              </boot_stats>
              <zigbee_state>
                <gateway_addr>%s!</gateway_addr>
                <caps>0x36b</caps>
                <pan_id>0x0000</pan_id>
                <ext_pan_id>0x0000000000000000</ext_pan_id>
                <channel>0xd</channel>
                <net_addr>0x0</net_addr>
                <association>0x0</association>
                <firmware_version>0x3119</firmware_version>
                <hardware_version>0x1941</hardware_version>
                <children>6</children>
                <max_payload>128</max_payload>
                <verify_cert>1</verify_cert>
                <stack_profile>2</stack_profile>
              </zigbee_state>
              <device_registry>
                <ethernet>on</ethernet>
              </device_registry>
            </query_state>
        """ % (int(time.clock()), settings.get('my_ipaddress','0.0.0.0'), eui)
        # print retval
        return retval
    except Exception, e:
        print "query_state: %s" % str(e)
        return ''
