from __future__ import annotations
import threading
from logging import Logger

from usbipice.worker import WorkerDatabase
from usbipice.utils import DeviceEventSender
from usbipice.utils.dev import *

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from usbipice.worker.device import Device

class EventMethod:
    def __init__(self, method, parms):
        self.method = method
        self.parms = parms

    def __call__(self, device, data):
        args = list(map(data.get, self.parms))

        if None in args:
            return False

        return self.method(device, *args)

class AbstractState:
    methods = {}

    def __init__(self, state: Device):
        """NOTE: switch CANNOT be called inside __init__(). This will result
        in the lock for Device being a acquired a second time. If this behavior 
        is needed, use start() instead."""
        super().__init__()
        self.state = state
        self.switching = False
        self.switching_lock = threading.Lock()

        self.reference_cv = threading.Condition()
        self.references = 0

        name = type(self).__name__
        self.getLogger().debug(f"state is now {name}")

    def start(self):
        """Called after the AbstractState is initialized, for
        actions that may result in a switch call."""

    def handleAdd(self, dev: dict):
        """Called on ADD device event."""

    def handleRemove(self, dev: dict):
        """Called on REMOVE device event."""

    def enableKernelAdd(self):
        self.getState().enableKernelAdd()

    def handleKernelAdd(self, dev: dict):
        """Called on a kernel dev add event. Unlike handleAdd, this is called on all
        dev events, not just ones that match this devices serial. This must be enabled with
        enableKernelAdd.
        """

    def disableKernelAdd(self):
        self.getState().disableKernelAdd()

    def enableKernelRemove(self):
        self.getState().enableKernelRemove()

    def handleKernelRemove(self, dev: dict):
        """Called on a kernel dev add event. Unlike handleAdd, this is called on all
        dev events, not just ones that match this devices serial. This must be enabled with
        enableKernelRemove.
        """

    def disableKernelRemove(self):
        self.getState().disableKernelRemove()

    def handleExit(self):
        """Cleanup"""
        self.disableKernelAdd()
        self.disableKernelRemove()

    def getState(self) -> Device:
        return self.state

    def getSerial(self) -> str:
        return self.getState().getSerial()

    def getLogger(self) -> Logger:
        return self.getState().getLogger()

    def getDatabase(self) -> WorkerDatabase:
        return self.getState().getDatabase()

    def getNotif(self) -> DeviceEventSender:
        return self.getState().getNotif()

    def switch(self, state_factory):
        # prevents multiple switches
        # from happening
        with self.switching_lock:
            if self.switching:
                return

            self.switching = True

            return self.getState().switch(state_factory)

    def isSwitching(self) -> bool:
        return self.switching

    def getSwitchingLock(self) -> threading.Lock:
        return self.switching_lock

    @classmethod
    def register(cls, event, *args):
        """Adds a method to the methods dictionary, which allows it to be called 
        using the handleEvent function with event=event. These arguments specify which json 
        key should be used to get the value of that positional argument when handleEvent is called.

        Ex. 
        >>> class ExampleDevice:  
                @AbstractState.register("add", "value 1", "value 2")  
                def addNumbers(self, a, b):  
                    self.getLogger().info(a + b)
        >>> requests.get("{host}/event", json={
                "serial": "ABCDEF",
                "value 1": 1,
                "value 2": 2
            })
        [ABCDEF] 3
        """
        class Reg:
            def __init__(self, fn):
                self.fn = fn

            def __set_name__(self, owner, name):
                if owner not in cls.methods:
                    cls.methods[owner] = {}

                if name in cls.methods[owner]:
                    raise Exception(f"{event} already registered")

                cls.methods[owner][event] = EventMethod(self.fn, args)
                setattr(owner, name, self.fn)

        return Reg

    def handleRequest(self, event, json):
        """Calls method event from the methods dictionary, using the arguments it was registered with 
        as keys for the json."""
        methods = AbstractState.methods.get(type(self))

        if not methods:
            return False

        method = methods.get(event)

        if method:
            return method(self, json)

        return False
