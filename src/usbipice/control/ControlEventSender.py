from usbipice.worker import EventSender

class ControlEventSender(EventSender):
    """Allows for sending event notifications to client's event server, as well as sending 
    instructions to worker's servers.."""
    def sendDeviceReservationEnd(self, serial: str, client_id: str) -> bool:
        """Sends a reservation end event for serial."""
        return self.sendClientJson(client_id, serial, {
            "event": "reservation end",
        })

    def sendDeviceFailure(self, serial: str, client_id: str) -> bool:
        """Sends a failure event for serial."""
        return self.sendClientJson(client_id, serial, {
            "event": "failure",
        })

    def sendDeviceReservationEndingSoon(self, serial: str) -> bool:
        """Sends a reservation ending soon event for serial."""
        return self.sendSerialJson(serial, {
            "event": "reservation ending soon",
        })
