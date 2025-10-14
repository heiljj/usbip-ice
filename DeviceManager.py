import pyudev
import re
import subprocess
from threading import Lock
import os
import shutil

from utils import *

class Firmware:
    def __init__(self, name, file, callback=None):
        self.name = name
        self.file = file
        self.callback = callback
    
class Device:
    def __init__(self, serial, logger, dev_files={}, export_usbip=False):
        self.serial = serial
        self.logger = logger
        self.dev_files = dev_files

        self.available = True
        self.lock = Lock()

        self.export_usbip = export_usbip
        self.exported_busid = None

        self.next_firmware = None
        self.current_firmware_name = None
        self.firmware_callback = None
    
    def handleAddDevice(self, udevinfo):
        if self.next_firmware:
            self.handleBootloaderMode(udevinfo)

        identifier = udevinfo.get("DEVNAME")

        if not identifier:
            self.logger.error(f"{format_dev_file(udevinfo)} addDevice: no devname in udevinfo, ignoring")
            return
        
        if identifier in self.dev_files.keys():
            self.logger.error(f"device {format_dev_file({udevinfo})} added but already exists, overwriting")
        
        self.dev_files[identifier] = udevinfo
        self.logger.info(f"added dev file {format_dev_file(udevinfo)}")

        # If in firmware mode, we can't export to usbip. 
        # This will cause a the bootloader bus to be exported when the disk
        # dev file is added, which means that we can no longer the partition dev files
        # on the same bus
        if not self.export_usbip or self.next_firmware:
            return

        busid = get_busid(udevinfo)

        binded = usbip_bind(busid)

        if not binded:
            self.logger.error(f"{format_dev_file(udevinfo)} failed to export usbip (bus {busid})")
            return
        
        self.exported_busid = busid

    def handleRemoveDevice(self, udevinfo):
        identifier = udevinfo.get("DEVNAME")

        if not identifier:
            self.logger.error(f"{format_dev_file(udevinfo)} removeDevice: no devname in udevinfo, ignoring")
            return
        
        if identifier not in self.dev_files.keys():
            self.logger.error(f"{format_dev_file(udevinfo)} removeDevice: dev file under major/minor does not exist, ignoring")
            return
        
        del self.dev_files[identifier]

        self.logger.info(f"removed device {format_dev_file(udevinfo)}")

    def startBootloaderMode(self, firmware):
        """Starts the process of updating firmware. When the update is complete,
        the callback will be called with self as the only argument."""
        self.logger.info(f"updating firmware of {self.serial} to {firmware.name}")
        self.next_firmware = firmware

        # cleanup will only trigger ADD events for devices that are being exported
        files = list(self.dev_files.values())

        for file in files:
            self.handleBootloaderMode(file)

        if self.exported_busid:
            unbound = usbip_unbind(self.exported_busid)
            if unbound:
                self.logger.info(f"unbound bus {self.exported_busid}")
                self.exported_busid = None
            else:
                self.logger.error(f"failed to unbind bus {self.exported_busid} (was the device disconnected?)")

    def handleBootloaderMode(self, udevinfo):
        """Send bootloader signal to tty devices, attempts to upload firmware to disk partitions"""
        if not self.next_firmware:
            return 

        if udevinfo.get("SUBSYSTEM") == "tty":
            send_bootloader(udevinfo["DEVNAME"])
            self.logger.info(f"sending bootloader signal to {udevinfo["DEVNAME"]}")

        elif udevinfo.get("DEVTYPE") == "partition":
            self.logger.info(f"found bootloader candidate {udevinfo["DEVNAME"]} for {self.serial}")
            path = f"media/{self.serial}"
            if not os.path.isdir(path):
                os.mkdir(path)
            
            mounted = mount(udevinfo["DEVNAME"], f"media/{self.serial}")

            if not mounted:
                self.logger.warning(f"detected potential bootloader drive for {self.serial} device {format_dev_file(udevinfo)} but failed to mount")

            if os.listdir(path) != ["INDEX.HTM", "INFO_UF2.TXT"]:
                self.logger.warning(f"bootloader candidate {udevinfo["DEVNAME"]} for {self.serial} mounted but had unexpected files")
                unmounted = umount(path)

                if not unmounted:
                    self.logger.error(f"bootloader candidate {udevinfo["DEVNAME"]} for {self.serial} mounted but had unexpected files then failed to unmount")

                return
            
            save_path = self.next_firmware.file
            if not os.path.isfile(save_path):
                self.logger.error(f"firmware not found for {self.serial}")
                return
            
            subprocess.run(["sudo", "cp", save_path, path])
            unmounted = umount(path)

            if not unmounted:
                self.logger.error(f"uploaded firmware to {format_dev_file(udevinfo)} for {self.serial}")
                
            self.endBootloaderMode()
    
    def endBootloaderMode(self):
        """Cleanup after firmware is uploaded"""
        self.logger.info(f"updated firmware for {self.serial}")
        self.current_firmware_name = self.next_firmware.name
        os.remove(self.next_firmware.file)

        if self.next_firmware.callback:
            self.next_firmware.callback(self)

        self.next_firmware = None

    def reserve(self):
        with self.lock:
            if not self.available:
                return False
            
            self.available = False
            return True
    
    def unreserve(self):
        with self.lock:
            if self.available:
                return False
            
            self.available = True
            return True

class DeviceManager:
    def __init__(self, logger, export_usbip=False):
        self.logger = logger
        self.export_usbip = export_usbip
        self.devs = {}

        if not os.path.isdir("media"):
            os.mkdir("media")
        
        if not os.path.isdir("firmware"):
            os.mkdir("firmware")

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        observer = pyudev.MonitorObserver(monitor, lambda x, y : self.handleDevEvent(x, y), name='monitor-observer')
        observer.start()
        self.scan()
    
    def scan(self):
        """Trigger add events for devices that are already connected"""
        self.logger.info("Scanning for devices")
        context = pyudev.Context().list_devices()

        for dev in context:
            self.handleDevEvent("add", dev)
        self.logger.info("Finished scan")

    def handleDevEvent(self, action, dev):
        dev = dict(dev)
        devname = dev.get("DEVNAME")

        if not devname:
            return

        if not re.match("/dev/", devname) or re.match("/dev/bus/", devname):
            return

        id_model = dev.get("ID_MODEL")

        # TODO we should have a config file for this stuff
        if id_model != "RP2350" and id_model != 'pico-ice' and id_model != 'Pico':
            return 
        
        serial = dev.get("ID_SERIAL_SHORT")

        if not serial:
            return

        if action == "add":
            self.handleAddDevice(serial, dev)
        elif action == "remove":
            self.handleRemoveDevice(serial, dev)
        else:
            self.logger.warning(f"Unhandled action type {action} for {format_dev_file(dev)}")

    def handleAddDevice(self, serial, udevinfo):
        if serial not in self.devs:
            self.logger.info(f"Creating device with serial {serial}")
            self.devs[serial] = Device(serial, self.logger, export_usbip=self.export_usbip)
        
        self.devs[serial].handleAddDevice(udevinfo)

    def handleRemoveDevice(self, serial, udevinfo):
        if serial not in self.devs:
            self.logger.warning(f"tried to remove dev file {format_dev_file(udevinfo)} but does not exist")
            return
        
        self.devs[serial].handleRemoveDevice(udevinfo)
    
    def getDevices(self):
        values = []

        for d in self.devs.values():
            values.append(d.serial)
        
        return values
    
    def getDeviceExportedBuses(self, device_serial):
        dev = self.devs.get(device_serial)

        if not dev:
            return False
        
        return dev.exported_busid
    
    def getDevicesAvailable(self):
        values = []

        for d in self.devs.values():
            if d.available:
                values.append(d.serial)
        
        return values
    
    def reserve(self, device_serial):
        dev = self.devs.get(device_serial)

        if not dev:
            return False
        
        return dev.reserve()
    
    def unreserve(self, device_serial):
        dev = self.devs.get(device_serial)

        if not dev:
            return False
        
        return dev.unreserve()
    
    def uploadFirmware(self, device_serial, firmware):
        dev = self.devs.get(device_serial)

        if not dev:
            return False
        
        dev.startBootloaderMode(firmware)
        return True
    
    def uploadFirmwares(self, device_serial_list, firmware):
        return list(map(lambda x : self.uploadFirmware(x, firmware), device_serial_list))



        
        
