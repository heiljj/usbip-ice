from client.lib import EventServer, AbstractEventHandler
from client.drivers.usbip.UsbipHandler import UsbipHandler
from client.base.usbip import UsbipAPI
from client.util import DefaultEventHandler

class UsbipClient(UsbipAPI):
    def __init__(self, control_url, client_name, logger):
        super().__init__(control_url, client_name, logger)

        self.server = EventServer(logger)

        default = DefaultEventHandler(self.server, self, logger)
        usbip = UsbipHandler(self.server, self, logger)

        self.eh = [default, usbip]

    def reserve(self, amount):
        return super().reserve(amount, self.server.getUrl())

    def start(self, client_ip: str, client_port: str, event_handlers: list[AbstractEventHandler]=None):
        if event_handlers:
            for handler in event_handlers:
                self.eh.append(handler)

        self.server.start(client_ip, client_port, self.eh)

    def stop(self):
        self.server.stop()
