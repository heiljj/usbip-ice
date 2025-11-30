from logging import Logger

from usbipice.client.lib import EventServer, AbstractEventHandler, register, BaseAPI

class DefaultEventHandler(AbstractEventHandler):
    def __init__(self, event_server: EventServer, api: BaseAPI, logger: Logger):
        super().__init__(event_server)
        self.api = api
        self.logger = logger

    @register("reservation ending soon", "serial")
    def handleReservationEndingSoon(self, serial: str):
        """Attempts to extend the reservation of the device."""
        if self.api.extend([serial]):
            self.logger.info(f"refreshed reservation of {serial}")
        else:
            self.logger.error(f"failed to refresh reservation of {serial}")

    @register("reservation end", "serial")
    def handleReservationEnd(self, serial: str):
        """Prints a notification and removes the device from the client"""
        self.logger.info(f"reservation for device {serial} ended")
        self.api.removeSerial(serial)

    @register("failure", "serial")
    def handleFailure(self, serial: str):
        """Prints an error and removes the device from the client"""
        self.logger.error(f"device {serial} failed")
        self.api.removeSerial(serial)
