import threading
import uuid
from dataclasses import dataclass

from usbipice.worker.device.state.core import AbstractState, FlashState
from usbipice.worker.device.state.reservable import reservable

#TODO 
PULSE_FIRMWARE_PATH = ""

@dataclass
class Bitstream:
    location: str
    name: str

@reservable("pulsecount")
class PulseCountStateFlasher(AbstractState):
    def __init__(self, state):
        super().__init__(state)

        pulse_fac = lambda : PulseCountState(self.getState())
        self.switch(lambda : FlashState(self.getState(), PULSE_FIRMWARE_PATH, pulse_fac))

class PulseCountState(AbstractState):
    def __init__(self, state):
        super().__init__(state)
        self.getNotif().sendDeviceInitialized(self.getSerial())

        self.bitstream_queue: list[Bitstream] = []
        self.results = {}
        self.cv = threading.Condition()

    @AbstractState.register("evaluate", "files")
    def queue(self, files):
        media_path = self.getState().getMediaPath()
        paths = [str(uuid.uuid4()) for _ in range(len(files))]

        for path, tmp in zip(paths, files.values()):
            save_path = str(media_path.joinpath(path))
            with open(save_path, "wb") as f:
                f.write(tmp.read())

        with self.cv:
            for path, name in zip(paths, files.keys()):
                self.bitstream_queue.append(Bitstream(path, name))

            self.cv.notify_all()
        #TODO