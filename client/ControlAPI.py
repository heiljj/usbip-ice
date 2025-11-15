import requests
from threading import Lock

class ConnectionInfo:
    def __init__(self, ip, usbipport, serverport):
        self.ip = ip
        self.usbipport = usbipport
        self.serverport = serverport
class ControlAPI:
    def __init__(self, url, name, logger):
        self.url = url
        self.name = name
        self.serials = set()
        self.lock = Lock()
        self.logger = logger
    
    def addSerial(self, serial):
        with self.lock:
            self.serials.add(serial)
    
    def removeSerial(self, serial):
        with self.lock:
            if serial in self.serials:
                self.serials.remove(serial)
                return True
            
            return False
    
    def getSerials(self):
        return self.serials

    def __requestControl(self, endpoint, data):
        try:
            res = requests.get(f"{self.url}/{endpoint}", json=data)

            if res.status_code != 200:
                self.logger.error(f"failed to GET /{endpoint}")
                return False
            
            return res.json()
        except Exception:
            return False
    
    def reserve(self, amount, subscription_url):
        """Returns serial -> (ConnectionInfo, bus)"""
        data = self.__requestControl("reserve", {
            "amount": amount,
            "name": self.name,
            "url": subscription_url 
        })

        if data == False:
            return False
        
        out = {}

        for row in data:
            self.addSerial(row["serial"])
            out[row["serial"]] = (ConnectionInfo(row["ip"], row["usbipport"], row["serverport"]), row["bus"])
        
        return out

    def extend(self, serials):
        return self.__requestControl("extend", {
            "name": self.clientname,
            "serials": serials
        })

    def extendAll(self):
        return self.__requestControl("extendall", {
            "name": self.clientname
        })

    def end(self, serials):
        if type(serials) != list:
            serials = list(serials)

        json = self.__requestControl("end", {
            "name": self.clientname,
            "serials": serials
        })

        if json == False:
            return False
        
        for serial in json:
            self.removeSerial(serial)
        
        return json
        
    def endAll(self):
        json = self.__requestControl("endall", {
            "name": self.clientname
        })

        if json == False:
            return False
        
        for serial in json:
            self.removeSerial(serial)
        
        return json
        
