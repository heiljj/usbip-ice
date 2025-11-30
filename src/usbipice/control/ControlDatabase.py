from logging import Logger

import psycopg
import requests

from usbipice.utils import Database

class ControlDatabase(Database):
    def __init__(self, dburl: str, logger: Logger):
        super().__init__(dburl)
        self.logger = logger

    def getDeviceWorkerUrl(self, serial: str) -> str:
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
        url = self.getDeviceWorkerUrl(serial)

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
