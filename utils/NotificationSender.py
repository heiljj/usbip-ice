from logging import Logger

import psycopg
import requests

from utils.Database import Database

class NotificationSender(Database):
    """Allows for sending event notifications to client's event server, as well as sending 
    instructions to worker's servers.."""
    def __init__(self, dburl: str, logger: Logger):
        super().__init__(dburl)
        self.logger = logger

    def __getDeviceSubscriptionUrl(self, deviceserial: str) -> str:
        """Returns the event server url for a device, None if there is none, or False on error."""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM getDeviceCallback(%s::varchar(255))", (deviceserial,))
                    data = cur.fetchall()
        except Exception:
            self.logger.warning(f"failed to get device callback for serial {deviceserial}")
            return False

        if not data:
            # no reservation
            return None

        return data[0][0]

    def __sendDeviceSubscription(self, deviceserial: str, contents: dict) -> bool:
        """Sends a GET request with json=contents to the event server of the device. 
        Returns whether successful."""
        url = self.__getDeviceSubscriptionUrl(deviceserial)

        if not url:
            return False

        try:
            res = requests.get(url, json=contents, timeout=10)
            if res.status_code != 200:
                raise Exception

        except Exception:
            self.logger.warning(f"failed to send subscription update for {deviceserial} to {url}")
            return False
        else:
            self.logger.debug(f"sent subscription update for {deviceserial} to {url}")
            return True

    def sendDeviceExport(self, serial: str, bus: str) -> bool:
        """Sends a device export event for serial with bus."""
        return self.__sendDeviceSubscription(serial, {
            "event": "export",
            "serial": serial,
            "bus": bus
        })

    def sendDeviceDisconnect(self, serial: str) -> bool:
        """Sends a device disconnect event for serial."""
        return self.__sendDeviceSubscription(serial, {
            "event": "disconnect",
            "serial": serial
        })

    def sendDeviceReservationEndingSoon(self, serial: str) -> bool:
        """Sends a reservation ending soon event for serial."""
        return self.__sendDeviceSubscription(serial, {
            "event": "reservation ending soon",
            "serial": serial
        })

    def sendDeviceReservationEnd(self, serial: str) -> bool:
        """Sends a reservation end event for serial."""
        return self.__sendDeviceSubscription(serial, {
            "event": "reservation end",
            "serial": serial
        })

    def sendDeviceFailure(self, serial: str) -> bool:
        """Sends a failure event for serial."""
        return self.__sendDeviceSubscription(serial, {
            "event": "failure",
            "serial": serial
        })

    def __getDeviceWorkerUrl(self, serial: str) -> str:
        """Obtains the worker server url of the worker the device is located on."""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM getDeviceWorker(%s::varchar(255))", (serial,))
                    data = cur.fetchall()
        except Exception:
            self.logger.error(f"failed to get worker callback for device {serial}")
            return False

        if not data:
            return False

        ip = str(data[0][0])
        port = data[0][1]
        return f"http://{ip}:{port}"

    def sendWorkerUnreserve(self, serial: str) -> bool:
        """Sends an request for the serial to be unreserved from the worker,
        resulting in the usbip bus being unbound."""
        url = self.__getDeviceWorkerUrl(serial)

        if not url:
            self.logger.error(f"failed to fetch worker url for device {serial}")
            return False

        try:
            res = requests.get(f"{url}/unreserve", json={
                "serial": serial
            }, timeout=10)
            if res.status_code != 200:
                raise Exception
        except Exception:
            self.logger.error(f"failed to instruct worker {url} to unreserve {serial}")
            return False
        else:
            return True
