from __future__ import annotations
import threading
from logging import Logger


from waitress.server import create_server
from flask import Flask, request, Response

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from usbipice.client.lib import AbstractEventHandler

class Event:
    def __init__(self, serial, name, json):
        self.serial = serial
        self.name = name
        self.json = json

class EventServer:
    """Hosts a server for the workers and heartbeat process to send events to. When an event is received,
    it calls the corresponding method of the EventHandlers starting at the 0 index."""
    def __init__(self, logger: Logger):
        super().__init__()
        self.logger = logger

        self.server = None
        self.thread = None

        self.eventhandlers = []
        if not isinstance(self.eventhandlers, list):
            self.eventhandlers = [self.eventhandlers]

        self.ip = None
        self.port = None

    def getUrl(self) -> str:
        """Returns url for workers to send events to."""
        return f"http://{self.ip}:{self.port}"

    def sendEvent(self, event: Event):
        for eh in self.eventhandlers:
            eh.handleEvent(event)

    def start(self, ip: str, port: str, eventhandlers: list[AbstractEventHandler]):
        """Starts the event server."""
        self.ip = ip
        self.port = port
        self.eventhandlers = eventhandlers
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
            event_name = json.get("event")

            if not serial or not event_name:
                return Response(status=400)

            event = Event(serial, event_name, json)
            self.sendEvent(event)

            return Response(status=200)

        self.server = create_server(app,  port=self.port)
        self.thread = threading.Thread(target=self.server.run, name="eventserver")
        self.thread.start()

    def stop(self):
        """Stops the event server."""
        if self.server:
            self.server.close()

        if self.thread:
            self.thread.join()

        for eh in self.eventhandlers:
            eh.exit()
