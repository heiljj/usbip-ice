from usbipice.worker.device.state.core import AbstractState

class BrokenState(AbstractState):
    def __init__(self, state):
        super().__init__(state)
        self.getDatabase().updateDeviceStatus(self.getSerial(), "broken")
        self.getLogger().error("device is broken")
