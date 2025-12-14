from logging import Logger, LoggerAdapter
import threading
import time

import requests
import schedule

from usbipice.control import HeartbeatDatabase, ControlEventSender

# TODO get values from config
class HeartbeatConfig:
    def __init__(self):
        self.heartbeat_poll_seconds = 15
        self.timeout_poll_seconds = 15
        self.timeout_duration_seconds = 60
        self.reservation_poll_seconds = 30
        self.reservation_expiring_poll_seconds = 300
        self.reservation_expiring_notify_at_seconds = 20 * 60

    def getHeartbeatPoll(self):
        return self.heartbeat_poll_seconds

    def getTimeoutPoll(self):
        return self.timeout_poll_seconds

    def getTimeoutDuration(self):
        return self.timeout_duration_seconds

    def getReservationPoll(self):
        return self.reservation_poll_seconds

    def getReservationExpiringPoll(self):
        return self.reservation_expiring_poll_seconds

    def getReservationNotifyAt(self):
        return self.reservation_expiring_notify_at_seconds

class HeartbeatLogger(LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[Heartbeat] {msg}", kwargs

# TODO make this nicer, improve logging
class Heartbeat:
    def __init__(self, event_sender: ControlEventSender, database_url: str, config: HeartbeatConfig, logger: Logger):
        self.event_sender = event_sender
        self.logger = HeartbeatLogger(logger)
        self.database = HeartbeatDatabase(database_url, self.logger)
        self.config = config
        self.thread = None

    def start(self):
        self.__startHeartBeatWorkers()
        self.__startWorkerTimeouts()
        self.__startReservationTimeouts()
        self.__startReservationEndingSoon()

        def run():
            while True:
                schedule.run_pending()
                time.sleep(1)

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def __startHeartBeatWorkers(self):
        def do():
            def run():
                workers = self.database.getWorkers()

                if not workers:
                    return

                for name, ip, port in workers:
                    url = f"http://{ip}:{port}/heartbeat"
                    try:
                        req = requests.get(url, timeout=10)

                        if req.status_code != 200:
                            raise Exception
                    except Exception:
                        self.logger.error(f"{name} failed heartbeat check")
                    else:
                        self.database.heartbeatWorker(name)

            threading.Thread(target=run, name="heartbeat-worker", daemon=True).start()

        schedule.every(self.config.getHeartbeatPoll()).seconds.do(do)

    def __startWorkerTimeouts(self):
        def do():
            def run(heartbeat_poll=self.config.getHeartbeatPoll()):
                data = self.database.getWorkerTimeouts(heartbeat_poll)
                if data:
                    for serial, client_name, worker in data:
                        self.event_sender.sendDeviceFailure(serial, client_name)
                        self.logger.info(f"Worker {worker} failed; sent device failure for {serial}")

            threading.Thread(target=run, name="heartbeat-worker-timeouts", daemon=True).start()

        schedule.every(self.config.getTimeoutPoll()).seconds.do(do)

    def __startReservationTimeouts(self):
        def do():
            def run():
                if (data := self.database.getReservationTimeouts()):
                    for serial, client_id in data:
                        self.event_sender.sendDeviceReservationEnd(serial, client_id)
                        self.database.sendWorkerUnreserve(serial)
                        self.logger.info(f"Reservation for device {serial} by client {client_id} ended")

            threading.Thread(target=run, name="heartbeat-reservation-timeouts", daemon=True).start()

        schedule.every(self.config.getReservationPoll()).seconds.do(do)

    def __startReservationEndingSoon(self):
        def do():
            def run(notify_at=self.config.getReservationNotifyAt()):
                if (data := self.database.getReservationEndingSoon(notify_at)):
                    for serial in data:
                        self.event_sender.sendDeviceReservationEndingSoon(serial)
                        self.logger.info(f"Sent ending soon notification for {serial}")

            threading.Thread(target=run, name="heartbeat-reservation-ending-soon", daemon=True).start()

        schedule.every(self.config.getReservationPoll()).seconds.do(do)
