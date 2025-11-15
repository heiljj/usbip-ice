import argparse
import os
import logging
import sys
import signal

from client.Client import Client
from client.EventHandler import DefaultEventHandler
from client.TimeoutDetector import TimeoutDetector


def main():
    parser = argparse.ArgumentParser(
        prog="Usbipice client cli",
        description="Connect to remote devices without having to modify existing systems"
    )

    parser.add_argument("amount", help="Amount of devices to connect to")
    parser.add_argument("clientname", help="Name of client")
    parser.add_argument("-f", "-firmware", help="Firmware path to upload to devices")
    parser.add_argument("-p", "-port", help="Port to host subscription server", default="8080")
    parser.add_argument("-c", "-controlserver", help="Control server hostname")
    args = parser.parse_args()

    amount = int(args.amount)
    port = args.p
    name = args.clientname
    firmware = args.f
    curl = args.c

    if not curl:
        curl = os.environ.get("USBIPICE_CONTROL_SERVER")
        if not curl:
            raise Exception("USBIPICE_CONTROL_SERVER not configured, set to url of the control server")

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    
    client = Client(name, curl, logger)
    eh = [TimeoutDetector(client, logger), DefaultEventHandler(logger)]

    logger.info("Starting event service...")
    client.startEventServer(eh, port=port)

    logger.info("Reserving devices...")
    serials = client.reserve(amount)

    def handler(sig, frame):
        logger.info("Ending reservations...")
        client.end(serials)

        logger.info("Stopping service...")
        client.stopEventServer()

        logger.info("Session ended.")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handler)

    if not serials:
        logger.error("Failed to reserve any devices.")
        sys.exit(1)

    if len(serials) != amount:
        logger.error(f"Requested {amount} devices but only got {len(serials)}. Ending reservation and exiting.")
        client.end(serials)
        sys.exit(1)
    
    logger.info(f"Successfully reserved {amount} devices.")
    
    if firmware:
        logger.info("Flashing devices...")

        failed = client.flash(serials, firmware, 240)

        if failed:
            logger.error(f"{len(failed)} devices failed to flash. Ending reservation and exiting.")
            client.end(serials)
            sys.exit(1)
        
        logger.info("Flashing successful!")
    
    logger.info("Devices are now ready.")

if __name__ == "__main__":
    main()
