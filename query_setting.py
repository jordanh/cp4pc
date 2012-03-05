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

# DEVNOTES
# socket.getfqdn() for my hostname
# socket.inet_ntoa and .inet_aton exist for converting packed 4-byte struct in_addr to/from dotted quad
# socket.getsockname() to get the local address; returns a (host, port) pair


from simulator_settings import settings

def query_setting():
    try:
        return """
            <query_setting>
              <boot>
                <eth_speed>auto</eth_speed>
                <eth_duplex>auto</eth_duplex>
                <dhcp>on</dhcp>
                <ip>%s</ip>
                <subnet>255.255.255.0</subnet>
                <gateway>10.40.18.1</gateway>
                <autoip>on</autoip>
                <addp>off</addp>
                <static>on</static>
              </boot>
              <system>
                <contact>Michael.Sutherland@digi.com
                </contact>
                <location>Davis, CA, U.S.A.</location>
                <description>%s</description>
              </system>
              <devicesecurity>
                <identityVerificationForm>simple</identityVerificationForm>
                <discoveryCodingScheme>noneNone</discoveryCodingScheme>
                <messagePassingScheme>noneNone</messagePassingScheme>
                <clientKeySize>128Bit</clientKeySize>
              </devicesecurity>
              <mgmtglobal>
                <deviceid>0x%s
                </deviceid>
                <rciCompressionEnabled>off</rciCompressionEnabled>
                <tcpNodelayEnabled>off</tcpNodelayEnabled>
                <tcpKeepalivesEnabled>off</tcpKeepalivesEnabled>
                <connIdleTimeout>0</connIdleTimeout>
                <dataServiceEnabled>on</dataServiceEnabled>
                <dataServicePort>80</dataServicePort>
                <dataServiceSecurePort>443</dataServiceSecurePort>
                <dataServiceUrl>/ws/device</dataServiceUrl>
              </mgmtglobal>
              <mgmtnetwork>
                <networkType>modemPPP</networkType>
                <connectMethod>mt</connectMethod>
                <mtRxKeepAlive>16</mtRxKeepAlive>
                <mtTxKeepAlive>16</mtTxKeepAlive>
                <mtWaitCount>3</mtWaitCount>
                <sslValidatePeer>off</sslValidatePeer>
              </mgmtnetwork>
              <mgmtnetwork index="2">
                <networkType>ethernet</networkType>
                <connectMethod>0x00A0 len=1164 mt</connectMethod>
                <mtRxKeepAlive>16</mtRxKeepAlive>
                <mtTxKeepAlive>16</mtTxKeepAlive>
                <mtWaitCount>3</mtWaitCount>
                <sslValidatePeer>off</sslValidatePeer>
              </mgmtnetwork>
              <mgmtnetwork index="3">
                <networkType>802.11</networkType>
                <connectMethod>mt</connectMethod>
                <mtRxKeepAlive>16</mtRxKeepAlive>
                <mtTxKeepAlive>16</mtTxKeepAlive>
                <mtWaitCount>3</mtWaitCount>
                <sslValidatePeer>off</sslValidatePeer>
              </mgmtnetwork>
              <mgmtconnection>
                <connectionType>client</connectionType>
                <connectionEnabled>on</connectionEnabled>
                <serverArray>
                  <serverAddress>en://%s
                  </serverAddress>
                  <securitySettingsIndex>0</securitySettingsIndex>
                </serverArray>
              </mgmtconnection>
              <mgmtconnection index="2">
                <connectionType>timed</connectionType>
                <connectionEnabled>off</connectionEnabled>
              </mgmtconnection>
                <mgmtconnection index="3">
                  <connectionType>serverInitiated</connectionType>
                  <connectionEnabled>off</connectionEnabled>
                </mgmtconnection>
                <interface name="eth0">
                  <eth_speed>auto</eth_speed>
                  <eth_duplex>auto</eth_duplex>
                  <dhcp>on</dhcp>
                  <ip>10.40.18.118</ip>
                  <subnet>255.255.255.0</subnet>
                  <gateway>10.40.18.1</gateway>
                  <autoip>on</autoip>
                  <addp>off</addp>
                  <static>on</static>
                </interface>
            </query_setting>
        """ % (settings.get('my_ipaddress','0.0.0.0'), settings["device_name"], settings["device_id"].replace("-", ""), settings['idigi_server'])
    except Exception, e:
        print "query_setting: %s" % str(e)
