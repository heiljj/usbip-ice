from usbipice.client.lib import AbstractEventHandler, register, BaseClient

class BaseUsbipEventHandler(AbstractEventHandler):
    @register("export", "serial", "busid", "server_ip", "usbip_port")
    def export(self, serial:str, busid: str, usbip_port: str):
        """Event signifies that a bus is now available through usbip
        for the client to connect to."""

    @register("disconnect", "serial")
    def disconnect(self, serial: str):
        """Event signifies that the worker has detected a usbip disconnection
        for this serial. This detection is often delayed - it is possible that
        when a device is disconnected and then reconnected, the client receives
        the export event before the disconnect one."""

class UsbipBaseClient(BaseClient):
    def reserve(self, amount):
        return super().reserve(amount, "usbip", {})

    def unbind(self, serial):
        return self.requestWorker(serial, "unbind", {})
