"""
Utility functions that don't fit the other modules.
"""
from __future__ import annotations
from logging import Logger
import re
import subprocess
import os
import inspect
import types
from configparser import ConfigParser
from functools import wraps
import asyncio

from pexpect import fdpexpect
from flask import Response, request, jsonify
from socketio import AsyncServer

# TODO reorganize this

def get_env_default(var, default: str, logger: Logger):
    """Obtains an environment variable. If its not configured, it instead returns
    the default value and logs a warning message."""
    value = os.environ.get(var)

    if not value:
        value = default
        logger.warning(f"{var} not configured, defaulting to {default}")

    return value

def config_else_env(option: str, section: str, parser: ConfigParser, error=True, default=None):
    """Tries to find option from section of a .ini file. If it fails,
    it instead looks at the environment variable option. If this also
    fails, raises exception.."""
    if parser:
        if section in parser.sections():
            value = parser[section].get(option)
            if value:
                return value

    value = os.environ.get(option)
    if error:
        if not value:
            if default:
                return default
            raise Exception(f"Configuration error. Set {section}.{option} in the configuration or specify {option} as an environment variable.")

    return value

def check_default(devpath) -> bool:
    """Checks for whether a device is running the default firmware."""
    # TODO
    # Sometimes closing the fd takes a long time (> 10s) on some firmwares,
    # this might create issues. I'm not really sure what the cause is, I added
    # a read from stdio to the default firmware and it seems to fix the issue.
    # The same behavior happens from opening and closing the file in C.
    try:
        with open(devpath, "r") as f:
            p = fdpexpect.fdspawn(f, timeout=2)
            p.expect("default firmware", timeout=2)

    except Exception:
        return False

    return True

def get_ip() -> str:
    """Obtains local network ip from hostname -I."""
    res = subprocess.run(["hostname", "-I"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
    group = re.search("[0-9]{3}\\.[0-9]{3}\\.[0-9]\\.[0-9]{3}", str(res))
    if group:
        return group.group(0)

def typecheck(fn, args) -> bool:
    """Checks whether args are valid types for fn. Only works on classes
    and non nested list generics. For dict, only checks if arg is a dict."""
    params = inspect.signature(fn).parameters.values()

    if len(params) != len(args):
        return False

    for arg, param in zip(args, params):
        annotation = param.annotation

        if annotation is inspect._empty:
            continue

        if inspect.isclass(annotation):
            if not isinstance(arg, annotation):
                return False

            continue

        if not isinstance(annotation, types.GenericAlias):
            return False

        if annotation.__origin__ is dict:
            continue

        if annotation.__origin__ is not list or not isinstance(arg, list):
            return False

        if len(annotation.__args__) != 1:
            return False

        type_ = annotation.__args__[0]

        for value in arg:
            if not isinstance(value, type_):
                return False

    return True

def json_to_args(json, parameters):
    values = list(map(json.get, parameters))
    if any(map(lambda x : x is None, parameters)):
        return False

    return values

def inject_and_return_json(func):
    """Injects request json values into arguments. Uses argument names as the json key. Typechecks arguments,
    only classes are supported. Returns a status=400 if a key is missing or the typecheck fails.
    Returns status=200 on True and status=500 on false. Otherwise, returns flask.jsonify of the result."""
    parameter_strings = [] # func args as string
    parameters = inspect.signature(func).parameters.values()

    for param in parameters:
        parameter_strings.append(param.name)

    @wraps(func)
    def handler_wrapper(*args):
        if request.content_type != "application/json":
            return Response(status=400)
        try:
            json = request.get_json()
        except Exception:
            return Response(status=400)

        args = json_to_args(json, parameter_strings)

        if not typecheck(func, args):
            return Response(status=400)

        res = func(*args)
        if res is True or res is None:
            return Response(status=200)
        if res is False:
            return Response(status=500)

        return jsonify(res)

    return handler_wrapper

def flask_socketio_adapter_connect(func):
    """Adapter to allow flask_socketio.SocketIO eventhandlers to use the same interface as
    socketio.AsyncServer for @socketio.on("connect"). This is
    achieved by injecting an empty environment argument."""
    @wraps(func)
    def event_handler(*args):
        if len(args) == 1:
            return func(request.sid, {}, args[0])

        return func(*args)

    return event_handler

def flask_socketio_adapter_on(func):
    """Adapter to allow flask_socketio.SocketIO eventhandlers to use the same interface as
    socketio.AsyncServer for @socketio.on events. If only one argument is passed, request.sid is
    injected as the first argument. For the connection event, you must use
    flask_socketio_adapter_connection instead."""
    @wraps(func)
    def event_handler(*args):
        if len(args) == 1:
            return func(request.sid, args[0])

        return func(*args)

    return event_handler

class SyncAsyncServer(AsyncServer):
    """Adapter to allow flask_socketio.SocketIO to have the same interface as socketio.AsyncServer while
    running as an ASGI app"""
    def emit(self, event, data=None, to=None, room=None, skip_sid=None, namespace=None, callback=None, ignore_queue=False):
        return asyncio.run(super().emit(event, data, to, room, skip_sid, namespace, callback, ignore_queue))

    def sleep(self, seconds=0):
        return asyncio.run(super().sleep(seconds))

def generate_circuit(hz, build_dir, build_script="src/usbipice/utils/build.sh", pcf_path="src/usbipice/utils/pico_ice.pcf", clk=48000000):
    """Builds a circuit of approximately hz."""
    if not os.path.isdir(build_dir):
        os.mkdir(build_dir)

    incr = int((clk/hz) - 1)
    veri = f"""
    module top (
        input CLK,
        output ICE_27,
        output LED_R,
        output LED_B
    );
    reg [22:0] counter;
    reg out;
    always @(posedge CLK) begin
        counter <= counter + 1;

        if (counter >= {incr}) begin
            out <= 1'b1;
            counter <= 23'b00000000000000000000000;
        end else begin
            out <= 1'b0;
        end
    end

    assign ICE_27 = out;
    assign LED_R = counter[22];
    endmodule
    """

    with open(os.path.join(build_dir, "top.v"), "w") as f:
        f.write(veri)

    subprocess.run(["bash", build_script, build_dir, pcf_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    return os.path.join(build_dir, "top.bin"), clk / incr / 1000
