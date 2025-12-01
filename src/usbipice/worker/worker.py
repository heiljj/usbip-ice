"""Starts the worker."""
import logging
import sys
import atexit
import os
import tempfile

from waitress import serve
from flask import Flask, request, Response, jsonify

from usbipice.worker.device import DeviceManager
from usbipice.worker import WorkerDatabase

from usbipice.utils import DeviceEventSender

def main():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    DATABASE_URL = os.environ.get("USBIPICE_DATABASE")
    IP = os.environ.get("USBIPICE_EXPORTED_IP")
    SERVER_PORT = os.environ.get("USBIPICE_EXPORTED_SERVER_PORT")
    USBIP_PORT = os.environ.get("USBIPICE_EXPORTED_USBIP_PORT")
    CLIENT_NAME = os.environ.get("USBIPICE_CLIENT")

    if not DATABASE_URL:
        logger.critical("USBIPICE_DATABASE not configured, exiting")
        raise Exception("USBIPICE_DATABASE not configured")

    if not CLIENT_NAME:
        logger.critical("USBIPICE_CLIENT not configured, exiting")
        raise Exception("USBIPICE_CLIENT not configured")

    if not IP:
        logger.warning("USBIPICE_EXPORTED_IP not configured")
        raise Exception("USBIPICE_EXPORTED_IP not configured")

    if not SERVER_PORT:
        SERVER_PORT= 8080
        logger.warning(f"USBIPICE_EXPORTED_SERVER_PORT not configured, defaulting to {SERVER_PORT}")
    else:
        SERVER_PORT = int(SERVER_PORT)

    if not USBIP_PORT:
        logger.error("USBIPICE_EXPORTED_USBIP_PORT not configured")
        raise Exception("USBIPICE_EXPORTED_USBIP_PORT not configured")

    else:
        USBIP_PORT = int(USBIP_PORT)

    db = WorkerDatabase(DATABASE_URL, CLIENT_NAME, IP, SERVER_PORT, logger)
    notif = DeviceEventSender(DATABASE_URL, logger)
    manager = DeviceManager(db, notif, logger)

    atexit.register(manager.onExit)

    app = Flask(__name__)

    @app.get("/heartbeat")
    def heartbeat():
        return Response(status=200)

    @app.get("/reserve")
    def reserve():
        if request.content_type != "application/json":
            return Response(status=400)

        # TODO client
        try:
            json = request.get_json()
        except Exception:
            return Response(status=400)

        status = 200 if manager.reserve(json) else 400

        return Response(status=status)

    @app.get("/unreserve")
    def devices_bus():
        if request.content_type != "application/json":
            return Response(status=400)

        try:
            json = request.get_json()
        except Exception:
            return Response(status=400)

        serial = json.get("serial")

        if not serial:
            return Response(status=400)

        if manager.unreserve(serial):
            return Response(status=200)
        else:
            return Response(status=400)

    @app.get("/request")
    def unbind():
        if request.content_type == "application/json":
            try:
                json = request.get_json()
            except Exception:
                return Response(status=400)

            value = manager.handleRequest(json)
            if value is None:
                return Response(status=400)

            return jsonify(value)

        elif request.content_type.startswith("multipart/form-data"):
            json = {}
            for key in request.form:
                items = request.form.getlist(key)
                if len(items) != 1:
                    return Response(status=400)

                json[key] = items[0]

            if "files" in json:
                return Response(status=400)

            files = {}

            try:
                for key in request.files:
                    file = request.files.getlist(key)
                    if len(file) != 1:
                        raise Exception

                    file = file[0]

                    temp = tempfile.NamedTemporaryFile()
                    file.save(temp.name)
                    files[key] = temp
            except Exception:
                for file in files.values():
                    file.close()

                return Response(400)

            json["files"] = files

            value = manager.handleRequest(json)

            for file in files.values():
                file.close()

            if value is None:
                return Response(status=400)

            return jsonify(value)

        else:
            return Response(status=400)


    serve(app, port=SERVER_PORT)

if __name__ == "__main__":
    main()
