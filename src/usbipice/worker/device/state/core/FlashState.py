import threading

from usbipice.worker.device.state.core import AbstractState, BrokenState

from usbipice.utils.dev import send_bootloader, upload_firmware_path, get_devs

class FlashState(AbstractState):
    def __init__(self, state, firmware_path, next_state_factory, timeout=None):
        super().__init__(state)
        self.firmware_path = firmware_path
        self.next_state_factory = next_state_factory
        self.timer = None

        if timeout:
            self.timer = threading.Timer(timeout, lambda : self.switch(lambda : BrokenState(self.getDevice())))
            self.timer.daemon = True
            self.timer.name = f"{self.getSerial()}-flash-timeout"
            self.timer.start()

    def start(self):
        devs = get_devs().get(self.getSerial())
        if not devs:
            return

        for file in devs:
            if self.isSwitching():
                return

            self.handleAdd(file)

    def handleAdd(self, dev):
        devname = dev.get("DEVNAME")

        if not devname:
            self.getLogger().warning("add event with no devname")
            return

        if dev.get("SUBSYSTEM") == "tty":
            self.getLogger().debug("sending bootloader signal")
            send_bootloader(devname)
            return

        if dev.get("DEVTYPE") == "partition":
            self.getLogger().debug("found bootloader candidate")

            uploaded = upload_firmware_path(devname, self.getDevice().getMountPath(), self.firmware_path)

            if not uploaded:
                self.getLogger().error("failed to upload firmware")
                self.switch(lambda : BrokenState(self.getDevice()))
                return

            self.switch(self.next_state_factory)
