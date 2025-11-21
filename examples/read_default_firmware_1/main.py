import logging
import sys
import os
import time

import atexit
from pexpect import fdpexpect

from client.Client import Client
from client.EventHandler import DefaultEventHandler
from client.TimeoutDetector import TimeoutDetector

from utils.dev import get_dev_paths
from utils.utils import get_ip

#################################################
CLIENT_NAME = "read default example"
CLIENT_IP = get_ip() # local network ip - must be accessible by control/worker servers
CLIENT_PORT = "8080"
CONTROL_SERVER = ""

if not CONTROL_SERVER:
    CONTROL_SERVER = os.environ.get("USBIPICE_CONTROL_SERVER")
#################################################

if not (CLIENT_NAME and CLIENT_IP and CLIENT_PORT and CONTROL_SERVER):
    raise Exception("Configuration error.")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

client = Client(CLIENT_NAME, CONTROL_SERVER, logger)

# EventHandlers receive events starting at the 0 index.
event_handlers = []

# This EventHandler connects with usbip when devices are available.
# It also provides some logging capabilities.
# There are few situations where it should not be used.
event_handlers.append(DefaultEventHandler(logger))

# This EventHandler checks for a broken usbip state that is not detectable
# on the server. It enables the timeout event. There are few situations
# where it should not be used.
event_handlers.append(TimeoutDetector(client, logger))

client.startEventServer(event_handlers, CLIENT_IP, CLIENT_PORT)

serials = client.reserve(1)

# End the reservation on exit. If we don't,
# the devices will be inaccessible for the remainder
# of the reservation (~1h).
atexit.register(lambda : client.end(serials))

if not serials:
    raise Exception("Failed to reserve a device.")

# Serial of the reserved device
serial = serials[0]

# Give some time for usbip connections to happen.
# This should be done by making an EventHandler instead,
# but as a first example this is much simpler.
time.sleep(5)

# Returns a dict mapping pico2ice device serials to lists
# of their device files.
device_paths = get_dev_paths()

if serial not in device_paths:
    # If there's a lot of network latency this could happen.
    raise Exception("Unable to find device file.")

dev_path = device_paths[serial][0]

# Read from device
tty = os.open(dev_path, os.O_RDWR)
p = fdpexpect.fdspawn(tty, timeout=5)
p.expect("default firmware")
print("Got response from device!")
p.close()

# Stops EventServer threads and sends exit signal
# to EventHandlers so they can cleanup
client.stopEventServer()
