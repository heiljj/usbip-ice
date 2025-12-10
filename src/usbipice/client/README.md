# Client Usage

## Installation
Cloning is not required to use the client library, but it is needed for running examples.
```
pip install git+https://github.com/heiljj/usbip-ice.git
```

If usbip functionally is needed, the module needs to be installed. This can be done with ```sudo apt install linux-tools-[kernel release]```. The kernel release can be found with ```uname -r```.
```
sudo modprobe usbip_core
sudo modprobe usbip_host
sudo modprobe vhci_hcd
```
Note that these modules will be unloaded after rebooting. When using usbip, permission groups have to be changed or the client will have to be run with sudo. With the later option, you can run a venv with sudo through ```sudo .venv/bin/python3 file.py```. Keep in mind that this will change your environment variables.

Set USBIPICE_CONTROL_SERVER to the url of the control server. Note that the worker servers communicate directly with the client, so they need to be accessible from the client. The client also hosts a server to listen for events, which needs to be accessible from both workers and the control server.

See [examples](../../../examples/). Currently, the [pulse count driver example](../../../examples/pulse_count_driver/) is the only one that does not use usbip.

## Library Usage
- See [pulse count client](./drivers/pulse_count/PulseCountClient.py) for interfacing with pulse count devices
- See [usbip client](./drivers/usbip/UsbipClient.py) for interfacing with usbip devices
