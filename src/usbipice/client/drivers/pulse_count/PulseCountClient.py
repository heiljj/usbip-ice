import threading
import uuid

from usbipice.client.lib.pulsecount import PulseCountAPI, PulseCountEventHandler
from usbipice.client.lib import EventServer, register
from usbipice.client.utils import DefaultEventHandler

class PulseCountClient(PulseCountAPI):
    # TODO threadsafe evals
    """NOTE: this implementation is intended only for single threaded use.
        Evaluates bitstreams for pulse counts. Evaluation is done on each device."""
    def __init__(self, url, client_name, logger):
        super().__init__(url, client_name, logger)

        self.server = EventServer(logger)
        self.running = False

        default = DefaultEventHandler(self.server, self, logger)
        result = ResultHandler(self.server, self)

        self.eh = [default, result]

        self.cv = threading.Condition()
        self.results = {}
        self.uuid_map = {}
        self.remaining_serials = set()

    def reserve(self, amount):
        """Reserves amount of devices."""
        if not self.running:
            raise Exception("Event server not started")
        return super().reserve(amount, self.server.getUrl())

    def start(self, client_ip: str, client_port: str):
        """Starts the event server. This should be done before reserving devices."""
        self.server.start(client_ip, client_port, self.eh)
        self.running = True

    def stop(self):
        """Stops the event server and ends reservations. This should be done before the program exits,
        even if it is the result of an exception. If the reservations are not ended, they will remain
        unavailable for the duration of the reservation (~1h)."""
        self.server.stop()
        self.running = False
        self.endAll()

    def _addResult(self, serial, value):
        with self.cv:
            self.results[serial] = value
            self.remaining_serials.remove(serial)

            if not self.remaining_serials:
                self.cv.notify_all()

    def evaluate(self, bitstream_paths: list[str]) -> dict[dict[str, int]]:
        "Evaluates a list of bitstream paths on each device. Returns as {serial -> {path -> pulses}}."
        self.uuid_map = {}
        self.results = {}
        self.remaining_serials = set()

        for path in bitstream_paths:
            self.uuid_map[str(uuid.uuid4())] = path

        self.remaining_serials = self.getSerials()

        for serial in self.getSerials():
            if not super().evaluate(serial, self.uuid_map):
                raise Exception(f"failed to send serial {serial}")

        with self.cv:
            self.cv.wait_for(lambda : not self.remaining_serials)

        values = {}

        for key, value in self.results.items():
            paths = map(self.uuid_map.get, value.keys())
            values[key] = dict(zip(paths, value.values()))

        return values

class ResultHandler(PulseCountEventHandler):
    def __init__(self, event_server, client: PulseCountClient):
        super().__init__(event_server)
        self.client = client

    @register("results", "serial", "results")
    def results(self, serial: str, results: dict[str, int]):
        self.client._addResult(serial, results)
