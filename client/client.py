from flask import Flask, request, Response
import threading
from abc import ABC, abstractmethod
import subprocess
import requests
import pyudev
from utils.utils import get_serial

def service(port, eventhandler, client):
    app = Flask(__name__)

    @app.route("/")
    def handle():
        if request.content_type != "application/json":
            return Response(400)
        
        try:
            json = request.get_json()
        except:
            return Response(400)
        
        event = json.get("event")

        if not event:
            return Response(400)
        
        serial = json.get("serial")

        if not serial:
            return Response(400)

        match event:
            case "failure":
                eventhandler.handleFailure(serial)
            case "reservation end":
                eventhandler.handleReservationEnd(serial)
                pass
            case "export":
                connection_info = client.getConnectionInfo(serial)

                if not connection_info:
                    return Response(400)
                
                ip, port = connection_info

                bus = json.get("bus")

                if not bus:
                    return Response(400)

                eventhandler.handleExport(serial, bus, ip, port)
            case "disconnect":
                eventhandler.handleDisconnect(serial)
            case "reservation halfway":
                eventhandler.handleReservationHalfway(serial)
            case _:
                return Response(400)

    app.run(port=port)

class EventHandler(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def handleExport(self, serial, bus, worker_ip, worker_port):
        """This is called when the host worker exports a reserved device."""
        pass

    @abstractmethod
    def handleDisconnect(self, serial):
        """This is called when the host worker is no longer exporting the device with usbip.
        This can happen normally, for example, during reboot after a firmware change. However, 
        if it's unexpected something probably went wrong."""
        pass

    @abstractmethod
    def handleReservationEnd(self, serial):
        """This is called when a devices reservation ends. The device will be unbound from the workers side -
        there is no way to retain access to a device after the reservation is over."""
        pass

    @abstractmethod
    def handleReservationHalfway(self, serial):
        """This is called when a reservation is halfway over. It is intended to be used to extend
        the reservation time."""
        pass

    @abstractmethod
    def handleFailure(self, serial):
        """This is called when a device failure occurs that is unrecoverable, such as the host worker failing
        a heartbeat check. It is not possible to connect back to the device."""
        pass

class DefaultEventHandler(EventHandler):
    def __init__(self, client_name, control_server_url, logger):
        super().__init__()
        self.client_name = client_name
        self.control_server_url = control_server_url
        self.logger = logger
    
    def handleExport(self, serial, bus, worker_ip, worker_port):
        try:
            p = subprocess.run(["sudo", "usbip", "--tcp-port", worker_port, "attach", "-r", worker_ip, "-b", bus], timeout=5)
            if p.returncode != 0:
                raise Exception

        except:
            self.logger.error(f"failed to bind device {serial} on {worker_ip}:{bus}")
        else:
            self.logger.info(f"bound device {serial} on {worker_ip}:{bus}")
    
    def handleDisconnect(self, serial):
        self.logger.warning(f"device {serial} disconnected")
    
    def handleReservationHalfway(self, serial):
        try:
            res = requests.get(f"{self.control_server_url}/extend", data={
                "name": self.client_name,
                "serials": [serial]
            })

            if res.status_code != 200:
                raise Exception
        
        except:
            self.logger.error(f"failed to refresh reservation of {serial}")
        else:
            self.logger.info(f"refreshed reservation of {serial}")
    
    def handleReservationEnd(self, serial):
        self.logger.info(f"reservation for device {serial} ended")
    
    def handleFailure(self, serial):
        self.logger.error(f"device {serial} failed")
    

class Client:
    def __init__(self, clientname, control_server_url):
        # serial -> (ip, port)
        self.serial_locations = {}
        self.clientname = clientname
        self.control_server_url = control_server_url

        self.thread = None
    
    def getConnectionInfo(self, serial):
        """Returns the (ip, port) needed to connect to a device with usbip."""
        return self.serial_locations.get(serial)

    def startService(self, port, eventhandler):
        """Starts listening for device events on the specified port using the eventhandler."""
        self.thread = threading.Thread(target=lambda : service(port, eventhandler, self))
        self.thread.start()

    def reserve(self, amount):
        """Reserves and connects to the specified amount of devices and returns their serials.
        If there are not enough devices available, it will reserve as many as it can."""
        try:
            data = requests.get(f"{self.control_server_url}/reserve", data={
                "amount":amount,
                "name": self.name
            })

            json = data.json()
        except:
            return False
        
        connections = []

        for row in json:
            try:
                serial = row["serial"]
                ip = row["ip"]
                port = row["usbipport"]
                bus = row["bus"]

                p = subprocess.run(["sudo", "usbip", "--tcp-port", port, "attach", "-r", ip, "-b", bus], timeout=5)

                if p.returncode != 0:
                    raise Exception
                
                connections.append(serial)
                self.serial_locations[serial] = (ip, port)
            except:
                #TODO disconnect
                pass
        
        return connections

    def flash(serials, firmware_path):
        #TODO
        pass

    def getDevs(serials):
        """Returns a dict mapping device serials to list of dev file paths. This operation 
        looks through all available dev files and is intended to be only used once after reserving devices.
        If you are dealing with frequent dev file changes, you should use a pyudev MonitorObserver instead."""
        pass
        context = pyudev.Context.list_devices()
        for dev in context:
            pass
            #TODO
            

    def extend(serial):
        pass

    def extendAll(serial):
        pass

    def unreserve(serial):
        pass

    def unreserveAll(serial):
        pass

