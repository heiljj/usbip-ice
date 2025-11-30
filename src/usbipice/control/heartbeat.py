import logging
import sys
import os
from threading import Thread
import time

import requests
import schedule

from usbipice.utils import DeviceEventSender, get_env_default
from usbipice.control import HeartbeatDatabase

def main():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    DATABASE_URL = os.environ.get("USBIPICE_DATABASE")
    if not DATABASE_URL:
        logger.critical("USBIPICE_DATABASE not configured")
        raise Exception("USBIPICE_DATABASE not configured")

    HEARTBEAT_POLL = int(get_env_default("USBIPICE_HEARTBEAT_SECONDS", "15", logger))

    TIMEOUT_POLL = int(get_env_default("USBIPICE_TIMEOUT_POLL_SECONDS", "15", logger))
    TIMEOUT_DURATION = int(get_env_default("USBIPICE_TIMEOUT_DURATION_SECONDS", "60", logger))

    RESERVATION_POLL = int(get_env_default("USBIPICE_RESERVATION_POLL", "30", logger))

    RESERVATION_EXPIRING_POLL = int(get_env_default("USBIP_RESERVATION_EXPIRING_POLL_SECONDS", "300", logger))
    RESERVATION_EXPIRING_NOTIFY_AT = int(get_env_default("USBIP_RESERVATION_EXPIRING_NOTIFY_AT_MINUTES", "20", logger))

    database = HeartbeatDatabase(DATABASE_URL, logger)
    notif = DeviceEventSender(DATABASE_URL, logger)


    def heartbeat_workers():
        workers = database.getWorkers()

        if not workers:
            return

        for name, ip, port in workers:
            url = f"http://{ip}:{port}/heartbeat"
            try:
                req = requests.get(url, timeout=10)

                if req.status_code != 200:
                    raise Exception
            except Exception:
                logger.error(f"{name} failed heartbeat check")
            else:
                database.heartbeatWorker(name)

    def worker_timeouts():
        data = database.getWorkerTimeouts(TIMEOUT_DURATION)
        if data:
            for serial, url in data:
                notif.sendDeviceFailure(serial, url=url)

    def reservation_timeouts():
        if (data := database.getReservationTimeouts()):
            for serial, url in data:
                database.sendWorkerUnreserve(serial)

    def reservation_ending_soon():
        if (data := database.getReservationEndingSoon(RESERVATION_EXPIRING_NOTIFY_AT)):
            for serial in data:
                notif.sendDeviceReservationEndingSoon(serial)

    heartbeat_workers()
    worker_timeouts()
    reservation_timeouts()
    reservation_ending_soon()

    schedule.every(HEARTBEAT_POLL).seconds.do(lambda : Thread(target=heartbeat_workers, name="worker-heartbeat").start())
    schedule.every(TIMEOUT_POLL).seconds.do(lambda : Thread(target=worker_timeouts, name="worker-timeout").start())
    schedule.every(RESERVATION_POLL).seconds.do(lambda : Thread(target=reservation_timeouts, name="reservation-ending-notifications").start())
    schedule.every(RESERVATION_EXPIRING_POLL).seconds.do(lambda : Thread(target=reservation_ending_soon, name="reservation-expiring").start())

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
