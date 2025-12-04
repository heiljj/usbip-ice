# NOTE: image needs to be same as host
FROM ubuntu:questing-20251029
WORKDIR /usr/local/app

# sudo is installed since its used in subprocess.run
# udev for dev events
RUN apt-get update && apt-get install -y git python3 python3-pip python3-venv sudo make udev
# NOTE: this package needs to match the host kernel version
# NOTE: this package also varies by device
# contains usbip module
RUN apt-get install -y linux-tools-6.17.0-1004-raspi 

COPY ./ /usr/local/app/

RUN python3 -m venv .venv
RUN .venv/bin/pip install -e .

# picocom is needed to flash firmware
WORKDIR /usr/local/build
RUN git clone https://github.com/npat-efault/picocom.git
WORKDIR /usr/local/build/picocom
RUN make
RUN cp picocom /usr/bin
WORKDIR /usr/local/app

EXPOSE 8080
# NOTE: docker is being used to make deployments easier. it is in no way providing isolation
# docker run --rm -t -i --privileged -v /dev:/dev -v /lib/modules:/lib/modules -v /run/udev:/run/udev:ro -v /tmp:/tmp --network=host -it usbipice bash
# -v /dev:/dev for dev files
# -v /lib/modules:/lib/modules for usbip 
# -v /tmp:/tmp for storing client files
# -v /run/udev:/run/udev:ro to provide additional dev attributes (like ID_SERIAL)
# from https://stackoverflow.com/questions/41753218/udevadm-does-not-show-all-attributes-inside-a-docker-container