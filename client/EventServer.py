import threading
from logging import Logger

from waitress.server import create_server
from flask import Flask, request, Response

from client.Client import Client
from client.EventHandler import EventHandler

class EventServer:
    """Hosts a server for the workers and heartbeat process to send events to. When an event is received,
    it calls the corresponding method of the EventHandlers starting at the 0 index."""
    def __init__(self, client: Client, eventhandlers: list[EventHandler], logger: Logger):
        super().__init__()
        self.client = client
        self.logger = logger

        self.server = None
        self.thread = None

        self.eventhandlers = eventhandlers
        if not isinstance(self.eventhandlers, list):
            self.eventhandlers = [self.eventhandlers]

        self.ip = None
        self.port = None

    def getUrl(self) -> str:
        """Returns url for workers to send events to."""
        return f"http://{self.ip}:{self.port}"

    def __callEventhandlers(self, method: str, args: tuple):
        """Calls method on each eventhandler with unpacked args."""
        for eh in self.eventhandlers:
            getattr(eh, method)(*args)

    def start(self, ip: str, port: str):
        """Starts the event server."""
        self.ip = ip
        self.port = port
        app = Flask(__name__)


        @app.route("/")
        def handle():
            if request.content_type != "application/json":
                return Response(status=400)

            try:
                json = request.get_json()
            except Exception:
                return Response(status=400)

            serial = json.get("serial")
            event = json.get("event")

            if not serial or not event:
                return Response(status=400)

            match event:
                case "failure":
                    self.__callEventhandlers("handleFailure", (self.client, serial))
                case "reservation end":
                    self.__callEventhandlers("handleReservationEnd", (self.client, serial))
                case "export":
                    connection_info = self.client.getConnectionInfo(serial)

                    if not connection_info:
                        return Response(status=400)

                    bus = json.get("bus")

                    if not bus:
                        return Response(status=400)

                    self.__callEventhandlers("handleExport", (self.client, serial, bus, connection_info.ip, str(connection_info.usbip_port)))
                case "disconnect":
                    self.__callEventhandlers("handleDisconnect", (self.client, serial))
                case "reservation halfway":
                    self.__callEventhandlers("handleReservationEndingSoon", (self.client, serial))
                case _:
                    return Response(status=400)

            return Response(status=200)

        self.server = create_server(app,  port=self.port)
        self.thread = threading.Thread(target=self.server.run, name="eventserver")
        self.thread.start()

    def triggerExport(self, serial: str, bus: str, ip: str, port: str):
        """Triggers an export event. Used to connect to devices that are already being exported over usbip."""
        self.__callEventhandlers("handleExport", (self.client, serial, bus, ip, str(port)))

    def triggerTimeout(self, serial: str, ip: str, port: str):
        """Triggers a timeout event. Used by the TimeoutDetector EventHandler to notify of timeouts."""
        self.__callEventhandlers("handleTimeout", (self.client, serial, ip, str(port)))

    def stop(self):
        """Stops the event server."""
        if self.server:
            self.server.close()

        if self.thread:
            self.thread.join()

        self.__callEventhandlers("exit", (self.client,))
