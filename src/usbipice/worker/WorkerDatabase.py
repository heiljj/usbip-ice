import psycopg
import requests

from usbipice.utils import Database, DeviceState

class WorkerDatabase(Database):
    """Provides access to database operations related to the worker process."""
    def __init__(self, dburl: str, clientname: str, exported_ip: str, exported_server_port: int, logger):
        super().__init__(dburl)
        self.clientname = clientname
        self.logger = logger

        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL addWorker(%s::varchar(255), %s::inet, %s::int)", (clientname, exported_ip, exported_server_port))
                    conn.commit()

        except Exception:
            logger.critical("Failed to add worker to database")
            raise Exception("Failed to add worker to database")


    def addDevice(self, deviceserial: str) -> bool:
        """Add a device to the database."""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL addDevice(%s::varchar(255), %s::varchar(255))", (deviceserial, self.clientname))
                    conn.commit()
        except Exception:
            self.logger.error(f"database: failed to add device with serial {deviceserial}")
            return False

        return True

    def updateDeviceStatus(self, deviceserial: str, status: DeviceState) -> bool:
        """Updates the status field of a device."""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("CALL updateDeviceStatus(%s::varchar(255), %s::DeviceState)", (deviceserial, status))
                    conn.commit()
        except Exception:
            self.logger.error(f"database: failed to update device {deviceserial} to status {status}")
            return False

    def onExit(self):
        """Removes the worker and all related devices from the database."""
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM removeWorker(%s::varchar(255))", (self.clientname,))
                    data = cur.fetchall()
        except Exception:
            self.logger.warning("failed to remove worker from db before exit")
            return

        for row in data:
            url, serial = row

            try:
                requests.get(url, data={
                    "event": "failure",
                    "serial": serial
                }, timeout=10)
            except Exception:
                self.logger.warning(f"failed to notify {url} of device {serial} failure")
