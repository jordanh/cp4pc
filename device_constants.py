# Device ID
DEVICE_ID = "00000000-00000000-DEAD01FF-FF00BEEF"
DEVICE_NAME = "PC SIMULATOR"
MAC = "\x00\x0F\xFE\x87\x46\x91"

# Default URI information 
HOST = "developer.idigi.com"
PORT = 3197
RECONNECT_TIME = 5 # in seconds

from simulator_settings import settings
DEVICE_ID = settings.get("device_id", DEVICE_ID)
DEVICE_NAME = settings.get("device_name", DEVICE_NAME)
HOST = settings.get("idigi_server", HOST)
PORT = settings.get("idigi_port", PORT)
