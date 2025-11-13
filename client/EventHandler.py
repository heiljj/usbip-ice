from abc import ABC, abstractmethod
import subprocess
import requests

from utils.utils import usbip_attach

class EventHandler(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def handleExport(self, client, serial, bus, worker_ip, worker_port):
        """This is called when the host worker exports a reserved device."""
        pass

    @abstractmethod
    def handleDisconnect(self, client, serial):
        """This is called when the host worker is no longer exporting the device with usbip.
        This can happen normally, for example, during reboot after a firmware change. However, 
        if it's unexpected something probably went wrong."""
        pass

    @abstractmethod
    def handleReservationEnd(self, client, serial):
        """This is called when a devices reservation ends. The device will be unbound from the workers side -
        there is no way to retain access to a device after the reservation is over."""
        pass

    @abstractmethod
    def handleReservationEndingSoon(self, client, serial):
        """This is called when a reservation is halfway over. It is intended to be used to extend
        the reservation time."""
        pass

    @abstractmethod
    def handleFailure(self, client, serial):
        """This is called when a device failure occurs that is unrecoverable, such as the host worker failing
        a heartbeat check. It is not possible to connect back to the device."""
        pass

class DefaultEventHandler(EventHandler):
    def __init__(self, client_name, control_server_url, logger):
        super().__init__()
        self.client_name = client_name
        self.control_server_url = control_server_url
        self.logger = logger
    
    def handleExport(self, client, serial, bus, worker_ip, worker_port):
        if usbip_attach(worker_ip, bus, tcp_port=worker_port):
            self.logger.info(f"bound device {serial} on {worker_ip}:{bus}")
        else:
            self.logger.error(f"failed to bind device {serial} on {worker_ip}:{bus} port {worker_port}")
    
    def handleDisconnect(self, client, serial):
        self.logger.warning(f"device {serial} disconnected")
    
    def handleReservationEndingSoon(self, client, serial):
        if client.extend([serial]):
            self.logger.info(f"refreshed reservation of {serial}")
        else:
            self.logger.error(f"failed to refresh reservation of {serial}")
    
    def handleReservationEnd(self, client, serial):
        self.logger.info(f"reservation for device {serial} ended")
    
    def handleFailure(self, client, serial):
        self.logger.error(f"device {serial} failed")