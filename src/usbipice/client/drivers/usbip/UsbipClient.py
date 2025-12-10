from usbipice.client.lib import EventServer, AbstractEventHandler
from usbipice.client.drivers.usbip import UsbipHandler
from usbipice.client.lib.usbip import UsbipAPI
from usbipice.client.utils import DefaultEventHandler

class UsbipClient(UsbipAPI):
    """Maintains a consistent usbip connection. Automatically reconnects to devices that temporarily stop exporting a device path."""
    def __init__(self, control_url, client_name, logger):
        super().__init__(control_url, client_name, logger)

        self.server = EventServer(logger)
        self.running = False

        default = DefaultEventHandler(self.server, self, logger)
        usbip = UsbipHandler(self.server, self, logger)

        self.eh = [default, usbip]

    def getEventServer(self) -> EventServer:
        return self.server

    def reserve(self, amount):
        """Reserves amount of devices."""
        if not self.running:
            raise Exception("Event server not started.")

        return super().reserve(amount, self.server.getUrl())

    def start(self, client_ip: str, client_port: str, event_handlers: list[AbstractEventHandler]=None):
        """Starts the event server. This should be done before reserving devices."""
        if event_handlers:
            for handler in event_handlers:
                self.eh.append(handler)

        self.server.start(client_ip, client_port, self.eh)
        self.running = True

    def stop(self):
        """Stops the event server. This should be done on program exit, even if as a result of an exception."""
        self.server.stop()
        self.running = False
        self.endAll()
