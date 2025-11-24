from abc import ABC, abstractmethod
import pyudev

class DeviceState:
    def __init__(self, serial, logger, database, notif):
        self.serial = serial
        self.logger = logger
        self.database = database
        self.notif = notif
        self.device = None #TODO flash

    def handleAdd(self, dev):
        self.device.handleAdd(dev)

    def handleRemove(self, dev):
        self.device.handleRemove(dev)

    def handleUnreserve(self):
        # TODO
        self.device.exit()

    def handleEvent(self, event, json):
        self.device.handleEvent(event, json)

    def switch(self, state_factory):
        self.device.handleExit()
        self.device = state_factory()

class EventMethod:
    def __init__(self, method, parms):
        self.method = method
        self.parms = parms

    def __call__(self, device, data):
        args = list(map(data.get, self.parms))

        if None in args:
            return False

        return self.method(device, *args)

class AbstractDevice(ABC):
    methods = {}

    def __init__(self, state: DeviceState):
        super().__init__()
        self.state = state

    @abstractmethod
    def handleAdd(self, dev: pyudev.Device):
        """Called on ADD device event."""

    @abstractmethod
    def handleRemove(self, dev: pyudev.Device):
        """Called on REMOVE device event."""

    @abstractmethod
    def handleExit(self):
        """Cleanup."""

    @classmethod
    def register(cls, event, *args):
        """Adds a method to the methods dictionary, which allows it to be called 
        using the handleEvent function with event=event. These arguments specify which json 
        key should be used to get the value of that positional argument when handleEvent is called.

        Ex. 
        >>> class ExampleDevice:  
                @AbstractDevice.register("add", "value 1", "value 2")  
                def addNumbers(self, a, b):  
                    return a + b  
        
        >>> ExampleDevice().handleEvent("add", {  
            "value 1": 1,  
            "value 2": 2  
        })  
        3
        """
        class Reg:
            def __init__(self, fn):
                self.fn = fn

            # hacky way to get reference to class
            # type within its own initiation
            def __set_name__(self, owner, name):
                if owner not in cls.methods:
                    cls.methods[owner] = {}

                if name in cls.methods[owner]:
                    raise Exception(f"{event} already registered")

                cls.methods[owner][event] = EventMethod(self.fn, args)
                setattr(owner, name, self.fn)
        return Reg

    def handleEvent(self, event, json):
        """Calls method event from the methods dictionary, using the arguments it was registered with 
        as keys for the json."""
        methods = AbstractDevice.methods.get(type(self))

        if not methods:
            return False

        method = methods.get(event)

        if method:
            return method(self, json)

        return False
