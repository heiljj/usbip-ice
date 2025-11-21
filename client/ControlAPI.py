from threading import Lock
from logging import Logger

import requests

class ConnectionInfo:
    """Database for information required to establish and maintain usbip connections."""
    def __init__(self, ip: str, usbip_port: str, server_port: str):
        self.ip = ip
        self.usbip_port = usbip_port
        self.server_port = server_port
class ControlAPI:
    """Provides an an abstraction over control server http endpoints and tracks reserved devices."""
    def __init__(self, url: str, client_name: str, logger: Logger):
        self.url = url
        self.name = client_name
        self.connection_info = {}
        self.lock = Lock()
        self.logger = logger

    def addSerial(self, serial, conn_info: ConnectionInfo):
        with self.lock:
            self.connection_info[serial] = conn_info

    def removeSerial(self, serial: str) -> bool:
        """Manually removes a device. Should be called after reservations end or 
        devices fail. Returns whether it was successful."""
        with self.lock:
            if serial in self.connection_info:
                del self.connection_info[serial]
                return True

        return False

    def getSerials(self) -> list[str]:
        """Returns tracked serials."""
        return list(self.connection_info.keys())

    def getConnectionInfo(self, serial: str) -> ConnectionInfo:
        """Returns connection information associated with a serial."""
        return self.connection_info.get(serial)

    def __requestControl(self, endpoint: str, json: dict) -> dict:
        """Sends a GET request to the specified endpoint of the control server with the specified json. Returns json of the response. 
        Returns False on error."""
        try:
            res = requests.get(f"{self.url}/{endpoint}", json=json, timeout=10)

            if res.status_code != 200:
                self.logger.error(f"failed to GET /{endpoint}")
                return False

            return res.json()
        except Exception:
            return False

    def reserve(self, amount: int, subscription_url: str) -> dict:
        """Reserves amount devices with subscription_url as a event server.
        Returns successful reservations as a dict of serial -> bus"""
        data = self.__requestControl("reserve", {
            "amount": amount,
            "name": self.name,
            "url": subscription_url 
        })

        if data is False:
            return False

        out = {}

        for row in data:
            serial = row["serial"]
            info = ConnectionInfo(row["ip"], row["usbipport"], row["serverport"])

            self.addSerial(serial, info)
            out[serial] = row["bus"]

        return out

    def extend(self, serials: list[str]) -> list[str]:
        """Extends the reservation on serials for by hour. The serials must be reserved under the client's name. 
        Returns the serials that were extended."""
        return self.__requestControl("extend", {
            "name": self.name,
            "serials": serials
        })

    def extendAll(self) -> list[str]:
        """Extends all reservations by the under the client's name for by hour. Returns the serials that were extended."""
        return self.__requestControl("extendall", {
            "name": self.name
        })

    def end(self, serials: list[str]) -> list[str]:
        """Ends the reservation on serials. The serials must be reserved under the client's name. Returns the serials of reservations
        that were ended."""
        if not isinstance(serials, list):
            serials = list(serials)

        json = self.__requestControl("end", {
            "name": self.name,
            "serials": serials
        })

        if json is False:
            return False

        for serial in json:
            self.removeSerial(serial)

        return json

    def endAll(self) -> list[str]:
        """Ends all reservations under the client's name. Returns the serials of reservations that were ended.."""
        json = self.__requestControl("endall", {
            "name": self.name
        })

        if json is False:
            return False
        
        for serial in json:
            self.removeSerial(serial)
        
        return json
        
