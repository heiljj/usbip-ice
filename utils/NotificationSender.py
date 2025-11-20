import psycopg
import requests

from utils.Database import Database

class NotificationSender(Database):
    def __init__(self, dburl, logger):
        super().__init__(dburl)
        self.logger = logger
    
    def __getDeviceSubscriptionUrl(self, deviceserial):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM getDeviceCallback(%s::varchar(255))", (deviceserial,))
                    data = cur.fetchall()
        except Exception:
            self.logger.warning(f"failed to get device callback for serial {deviceserial}")
            return False

        if not data:
            # no reservation
            return False
        
        return data[0][0]
    
    def __sendDeviceSubscription(self, deviceserial, contents):
        url = self.__getDeviceSubscriptionUrl(deviceserial)

        if not url:
            return False
        
        try:
            res = requests.get(url, json=contents)
            if res.status_code != 200:
                raise Exception

        except Exception:
            self.logger.warning(f"failed to send subscription update for {deviceserial} to {url}")
            return False
        else:
            self.logger.debug(f"sent subscription update for {deviceserial} to {url}")
            return True
    
    def sendDeviceExport(self, serial, bus):
        return self.__sendDeviceSubscription(serial, {
            "event": "export",
            "serial": serial,
            "bus": bus
        })
    
    def sendDeviceDisconnect(self, serial):
        return self.__sendDeviceSubscription(serial, {
            "event": "disconnect",
            "serial": serial
        })
    
    def sendDeviceReservationEndingSoon(self, serial):
        return self.__sendDeviceSubscription({
            "event": "reservation ending soon",
            "serial": serial
        })
    
    def sendDeviceReservationEnd(self, serial):
        return self.__sendDeviceSubscription(serial, {
            "event": "reservation end",
            "serial": serial
        })
    
    def sendDeviceFailure(self, serial):
        return self.__sendDeviceSubscription(serial, {
            "event": "failure",
            "serial": serial
        })
    
    def __getDeviceWorkerUrl(self, serial):
        try:
            with psycopg.connect(self.url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM getDeviceWorker(%s::varchar(255))", (serial,))
                    data = cur.fetchall()
        except Exception:
            self.logger.error(f"failed to get worker callback for device {serial}")
            return False
        
        if not data:
            return False
        
        ip = str(data[0][0])
        port = data[0][1]
        return f"http://{ip}:{port}"
    
    def sendWorkerUnreserve(self, serial):
        url = self.__getDeviceWorkerUrl(serial)

        if not url:
            self.logger.error(f"failed to fetch worker url for device {serial}")
            return False
        
        try:
            res = requests.get(f"{url}/unreserve", json={
                "serial": serial
            })
            if res.status_code != 200:
                raise Exception
        except Exception:
            self.logger.error(f"failed to instruct worker {url} to unreserve {serial}")
            return False
        else:
            return True
    




