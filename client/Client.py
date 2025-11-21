from logging import Logger

import requests

from client.ControlAPI import ControlAPI
from client.EventServer import EventServer
from client.EventHandler import EventHandler

class Client(ControlAPI):
    """Used to reserve and connect to devices. Provides a central place for EventHandlers to 
    access related methods for responding to events."""
    def __init__(self, clientname: str, control_server_url: str, logger: Logger):
        super().__init__(control_server_url, clientname, logger)
        self.logger = logger
        self.clientname = clientname
        self.event_server = None

    def startEventServer(self, event_handlers: list[EventHandler], ip: str, port: int=8080):
        """Starts the event server. When an event happens, the eventhandlers are notified starting with the 0 index and
        the corresponding method is called. The ip/port must be accessible by control and worker servers."""
        self.event_server = EventServer(self, event_handlers, self.logger)
        self.event_server.start(ip, port)

    def stopEventServer(self):
        """Stops the event server."""
        if self.event_server:
            self.event_server.stop()

    def reserve(self, amount: int) -> list[str]:
        """Reserves and connects to the specified amount of devices and returns their serials. Triggers export events for newly connected devices.
        If there are not enough devices available, it will reserve as there are available. Returns False on error."""
        if not self.event_server:
            raise Exception("event server not started")

        buses = super().reserve(amount, self.event_server.getUrl())

        if not buses:
            return False

        for serial in buses:
            conn_info = self.getConnectionInfo(serial)
            self.event_server.triggerExport(serial, buses[serial], conn_info.ip, conn_info.usbip_port)

        return list(buses.keys())


    def unbind(self, serial: str) -> bool:
        """Finds the worker server responsible for the specified device and instructs it to unbind the device.
        This can be be used if the worker thinks that the client is connected but it is not."""
        conn_info = self.getConnectionInfo(serial)
        if not conn_info:
            return False

        try:
            res = requests.get(f"http://{conn_info.ip}:{conn_info.server_port}/unbind", json={
                "serial": serial,
                "name": self.clientname
            }, timeout=10)

            if res.status_code != 200:
                raise Exception

            return True
        except Exception:
            return False

    def triggerTimeout(self, serial: str) -> bool:
        """Manually triggers a timeout event on the event server. Used by TimeoutDetector."""
        conn_info = self.getConnectionInfo(serial)

        if not conn_info:
            self.logger.error(f"device {serial} timed out but no connection information")
            return False

        self.event_server.triggerTimeout(serial, conn_info.ip, conn_info.server_port)
        return True
