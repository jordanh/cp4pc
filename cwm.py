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

