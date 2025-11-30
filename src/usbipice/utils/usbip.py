"""
Functions for running usbip and parsing output.
"""
import re
import subprocess

def usbipd(timeout: int=5):
    """Starts usbipd as a daemon."""
    try:
        subprocess.run(["sudo", "usbipd", "-D"], timeout=timeout, check=True)
    except Exception:
        pass

def usbip_bind(busid: str, timeout:int =10) -> bool:
    """Binds busid to usbip."""
    try:
        subprocess.run(["sudo", "usbip", "bind", "-b", busid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout, check=True)
    except Exception:
        return False
    
    return True

def usbip_unbind(busid: str, timeout:int =10) -> bool:
    """Unbinds busid from usbip."""
    try:
        subprocess.run(["sudo", "usbip", "unbind", "-b", busid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout, check=True)
    except Exception:
        return False

    return True

def usbip_attach(ip: str, busid: str, tcp_port: str="3240", timeout: int=20):
    """Attaches to bus on ip with usbip."""
    try:
        subprocess.run(["sudo", "usbip", "--tcp-port", str(tcp_port), "attach", "-r", ip, "-b", busid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout, check=True)
    except Exception:
        return False

    return True

def usbip_port(timeout=20) -> dict:
    """Obtains current usbip connections using usbip port and parses them as {ip -> [buses]}"""
    try:
        p = subprocess.run(["sudo", "usbip", "port"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout, check=True)

        connections = re.findall("usbip://.*?[0-9]+-(?:[0-9]|\\.)+", str(p.stdout))

        info = {}

        for c in connections:
            ip = re.search("usbip://(.*?):", c)
            bus = re.search(":[0-9]+/(.*)", c)

            if not ip or not bus:
                return

            ip = ip.group(1)
            bus = bus.group(1)

            if ip not in info:
                info[ip] = []

            info[ip].append(bus)

        return info

    except Exception:
        return False

def get_exported_buses(timeout=10) -> list:
    """Obtains the buses currently being exported and not being connected to on the local host."""
    try:
        p = subprocess.run(["usbip", "list", "-r", "localhost"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout, check=True)
    except Exception:
        return False

    return re.findall("([0-9]+-(?:[0-9]|\\.)+):", str(p.stdout))
