import pyudev
import threading
import os

from utils.dev import *
from utils.utils import *

class FirmwareFlasher:
    """Used to flash firmware."""
    def __init__(self):
        self.remaining_serials = {}
        self.uploading_serials = {}
        self.failed_serials = []

        self.path = None
        self.timeout = None
        self.timeout_thread = None
        self.exit= False

        self.data_lock = threading.Condition()

        if not os.path.exists("client_media"):
            os.mkdir("client_media")

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        self.observer = pyudev.MonitorObserver(monitor, lambda x, y: self.__handle_event(x, y), name="flash-observer")

    def startFlasher(self):
        """Start monitoring for device events."""
        if not self.observer.is_alive():
            self.observer.start()

    def flash(self, serials: list[str], path: str):
        """Queue serials to be flashed with path firmware. Note that this does not return when the devices 
        are done being flashed, only once the devices have been added into the queue."""
        if not isinstance(serials, list):
            serials = [serials]

        self.exit = False
        with self.data_lock:
            for serial in serials:
                self.remaining_serials[serial] = path

        info = get_devs()
        devs = []

        for serial, path in info.items():
            if serial in serials:
                devs.extend(path)


        for file in devs:
            if file.get("SUBSYSTEM") != "tty":
                return

            if (path := file.get("DEVNAME")):
                send_bootloader(path)

    def waitUntilFlashingFinished(self, timeout=None) -> tuple[list, list]:
        """Returns when all of the devices in the queue are done being flashed to, after timeout seconds, or if the flasher is stopped.
        Returns ([remaining serials], [failed serials]). Note that the remaining serials will still be flashed to,
        they have just not finished yet.
        """
        timer = None

        def ontimeout():
            with self.data_lock:
                self.exit = True
                self.data_lock.notify_all()

        if timeout:
            timer = threading.Timer(timeout, ontimeout)
            timer.start()

        with self.data_lock:
            self.data_lock.wait_for(lambda : (not self.remaining_serials and not self.uploading_serials) or self.exit)
            remaining = self.remaining_serials.keys()
            failed = self.failed_serials
            self.remaining_serials = {}
            self.failed_serials = []
            self.exit = False

        if timer:
            timer.cancel()

        return remaining, failed

    def stopFlasher(self):
        """Stops monitoring for device events. Signals calls to waitUntilFlashingFinished to return."""

        if self.observer.is_alive():
            self.observer.send_stop()
        self.exit = True

    def __handle_event(self, action, dev):
        """Pyudev event handler. Connects with baud 1200 picocom to tty devices, tries to upload firmware to partition devices."""
        if action != "add":
            return

        dev = dict(dev)

        if dev.get("SUBSYSTEM") == "tty":
            serial = get_serial(dev)

            with self.data_lock:
                if not serial or serial not in self.remaining_serials:
                    return

            devname = dev.get("DEVNAME")

            if not devname:
                return

            send_bootloader(devname)

        elif dev.get("DEVTYPE") == "partition":
            serial = get_serial(dev)

            with self.data_lock:
                if not serial or serial not in self.remaining_serials:
                    return

                path = self.remaining_serials[serial]

            devname = dev.get("DEVNAME")

            if not devname:
                return

            mount_path = os.path.join("client_media", serial)
            if not os.path.exists(mount_path):
                os.mkdir(mount_path)

            with self.data_lock:
                del self.remaining_serials[serial]
                self.uploading_serials[serial] = dev

            try:
                upload_firmware_path(devname, mount_path, path, mount_timeout=30)
                with self.data_lock:
                    if serial in self.uploading_serials:
                        del self.uploading_serials[serial]

            except FirmwareUploadFail:
                with self.data_lock:
                    self.failed_serials.append(serial)

                    if serial in self.uploading_serials:
                        del self.uploading_serials[serial]

            with self.data_lock:
                done = len(self.remaining_serials) == 0

            if done:
                self.exit = True
                with self.data_lock:
                    self.data_lock.notify_all()
