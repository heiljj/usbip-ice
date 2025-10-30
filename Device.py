import os

from utils import *

class Device:
    def __init__(self, serial, logger, database, dev_files={}):
        self.serial = serial
        self.logger = logger
        self.dev_files = dev_files
        self.database = database

        self.bootloader_mode = False
        self.exported_busid = None
    
    def handleAddDevice(self, udevinfo):
        if self.bootloader_mode:
            self.handleBootloaderMode(udevinfo)
            return

        identifier = udevinfo.get("DEVNAME")

        if not identifier:
            self.logger.error(f"{format_dev_file(udevinfo)} addDevice: no devname in udevinfo, ignoring")
            return
        
        if identifier in self.dev_files.keys():
            self.logger.error(f"dev file {format_dev_file({udevinfo})} added but already exists, overwriting")
        
        self.dev_files[identifier] = udevinfo
        self.logger.info(f"added dev file {format_dev_file(udevinfo)}")

        # If in firmware mode, we can't export to usbip. 
        # This will cause a the bootloader bus to be exported when the disk
        # dev file is added, which means that we can no longer the partition dev files
        # on the same bus
        if self.bootloader_mode:
            return

        busid = get_busid(udevinfo)
        self.logger.info(f"binded dev {format_dev_file(udevinfo)} on {busid}")
        binded = usbip_bind(busid)

        if not binded:
            self.logger.error(f"{format_dev_file(udevinfo)} failed to export usbip (bus {busid})")
            return
        
        self.exported_busid = busid
        
        if not self.database.updateDeviceBus(self.serial, busid):
            # TODO subscr error
            return

        # TODO subscr change

    def handleRemoveDevice(self, udevinfo):
        identifier = udevinfo.get("DEVNAME")

        if not identifier:
            self.logger.error(f"{format_dev_file(udevinfo)} removeDevice: no devname in udevinfo, ignoring")
            return
        
        if identifier not in self.dev_files.keys():
            self.logger.error(f"{format_dev_file(udevinfo)} removeDevice: dev file under major/minor does not exist, ignoring")
            return
        
        del self.dev_files[identifier]

        self.logger.info(f"removed dev file {format_dev_file(udevinfo)}")

    def handleUsbipDisconnect(self):
        self.exported_busid = None
        self.database.removeDeviceBus(self.serial)

    def startBootloaderMode(self):
        """Starts the process of updating firmware. When the update is complete,
        the callback will be called with self as the only argument."""
        self.logger.info(f"reflashing device {self.serial} to default firmware")
        self.bootloader_mode = True

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
                self.database.updateDeviceStatus(self.serial, "broken")
                return
        
        self.database.updateDeviceStatus(self.serial, "flashing_default")

        
    def handleBootloaderMode(self, udevinfo):
        """Send bootloader signal to tty devices, attempts to upload firmware to disk partitions"""
        if not self.bootloader_mode:
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
            
            subprocess.run(["sudo", "cp", "default_firmware.uf2", path])
            unmounted = umount(path)

            if not unmounted:
                self.logger.error(f"uploaded firmware to {format_dev_file(udevinfo)} for {self.serial}")
                
            self.endBootloaderMode()
    
    def endBootloaderMode(self):
        """Cleanup after firmware is uploaded"""
        self.logger.info(f"restored default firmware to {self.serial}")
        self.bootloader_mode = False

        # TODO confirm new firmware loaded
        self.database.updateDeviceStatus(self.serial, "available")
    