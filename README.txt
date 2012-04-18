README for the ConnectPort for PC (cp4pc) project.

Requirements:
1) Python 2.6 or newer - it won't work with Python 2.4.3 due to missing
   standard modules
2) pyserial - this is used to connect to the XBee
3) requires weob for the local webpage and ability to POST local code.

Over the years Digi engineers have been creating various Python tools which
emulate a Digi gateway - such as the CPX4.  These include ADDP, EDP and
XBee-like socket and DDO functions.  As of March 2012, one can even run the
iDigi/Dia with Xbee devices.

License:
Copyright (c) 2009-2012 Digi International Inc.
All rights not expressly granted are reserved.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
 
Digi International Inc. 11001 Bren Road East, Minnetonka, MN 55343

What works:
1) Your PC shows up via ADDP - so Digi Device Discovery utility will see and
   display it
2) Your PC uses EDP to iDigi, which with ADDP support means you can add your
   PC to your iDigi account using the web console. (Note: since the cp4pc
   will refuse to 'reboot', you'll get a warning during this addition - but
   it works)
3) Python scripts can make use of DDO and XB 'Socket' functions.
4) Support for ZB ZBee with the PC as the coordinator
5) normal iDigi/EDP upload works

What is unknown or TBD:
1) TBD - does DigiMesh and others work?
2) TBD - the PC does not appear to show up on the iDigi 'XBee Networks' page

Steps to use:

1) Add an XBee (XStick or XBIB) to your PC.  Flash the XBee with API
   Coordinator firmware, add settings:

	 BD=7 : Set a baud rate to 115,200
	 CE=1 : enable coordinator (this may be optional - TBD)
	 AP=1 : enable API mode
	 AO=3 : enable explicit messages with ZDO passthrough

2) Checkout and place the cp4pc directory in a convenient drive location,
   such as C:\Python26\Lib\site-packages\cp4pc

3) Add the cp4pc directory to your PYTHONPATH.  With Windows one option is to
   create a MSDOS batch file such as:

	set PATH=%PATH%;C:\Python26;
	set PYTHONPATH=C:\Python26\Lib\site-packages\serial;C:\Python26\Lib\site-packages\cp4pc;

4) EDIT the file named simulator_settings.py, which is in the root directory
   of the project cp4pc.  You must at least the following lines:

  # serial port settings for XBee
  settings['com_port'] = 'COM1' #default to first serial port.
  settings['baud'] = 115200

5) Your main script needs to import xbee.py as a whole, which adds the Digi
   XBee socket extensions to your PC's socket module.

6) If you are running Dia, then until Dia 2.0.x is released you will see an
   exception thrown because the xbee_device_manager.py uses one instance of the
   old constant socket.ZBS_PROT_TRANSPORT, which you can rename to the correct
   socket.XBS_PROT_TRANSPORT.

