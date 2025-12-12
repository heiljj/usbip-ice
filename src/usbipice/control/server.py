import os
import psycopg
import logging
import sys

import requests
from flask import Flask, request, Response, jsonify
from waitress import serve

from usbipice.control import ServerDatabase
from usbipice.utils import DeviceEventSender

def argify_json(parms: list[str]):
    """Obtains the json values of keys in the list from the flask Request and unpacks them into fun, starting with the 0 index."""
    if request.content_type != "application/json":
        return False
    try:
        json = request.get_json()
    except Exception:
        return False

    args = []

    for p in parms:
        value = json.get(p)
        if value is None:
            return False
        args.append(value)

    if len(args) != len(parms):
        return False

    return args

def expect(fn, arg):
    if not arg:
        return Response(status=400)

    return jsonify(fn(*arg))

def main():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    DATABASE_URL = os.environ.get("USBIPICE_DATABASE")
    if not DATABASE_URL:
        raise Exception("USBIPICE_DATABASE not configured")

    SERVER_PORT = int(os.environ.get("USBIPICE_CONTROL_PORT", "8080"))
    logger.info(f"Running on port {SERVER_PORT}")

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                pass
    except Exception:
        raise Exception("Failed to connect to database")

    database = ServerDatabase(DATABASE_URL, logger)
    notif = DeviceEventSender(DATABASE_URL, logger)
    app = Flask(__name__)

    @app.get("/reserve")
    def make_reservations():
        args = argify_json(["amount", "name", "kind", "args"])
        if not args:
            return Response(status=400)

        reservation_args = args.pop()
        kind = args.pop()

        data = database.reserve(*args)

        if not data:
            return Response(status=400)

        for row in data:
            ip = row["ip"]
            port = row["serverport"]
            serial = row["serial"]

            try:
                res = requests.get(f"http://{ip}:{port}/reserve", json={
                    "serial": serial,
                    "kind": kind,
                    "args": reservation_args
                }, timeout=5)

                if res.status_code != 200:
                    raise Exception
            except Exception:
                pass

        return jsonify(data)

    @app.get("/extend")
    def extend():
        return expect(database.extend, argify_json(["name", "serials"]))

    @app.get("/extendall")
    def extendall():
        return expect(database.extendAll, argify_json(["name"]))

    @app.get("/end")
    def end():
        args = argify_json(["name", "serials"])

        if not args:
            return Response(status=400)

        data = database.end(*args)

        if not data:
            return jsonify({})

        for row in data:
            notif.sendDeviceReservationEnd(row["subscriptionurl"], row["serial"])
            database.sendWorkerUnreserve(row["serial"])

        return jsonify(list(map(lambda x : x["serial"], data)))

    @app.get("/endall")
    def endall():
        args = argify_json(["name"])

        if not args:
            return Response(status=400)

        data = database.endAll(*args)

        if not data:
            return jsonify({})

        for row in data:
            notif.sendDeviceReservationEnd(row["subscriptionurl"], row["serial"])
            database.sendWorkerUnreserve(row["serial"])

        return jsonify(list(map(lambda x : x["serial"], data)))

    @app.get("/log")
    def log():
        args = argify_json(["logs", "name"])
        if not args:
            return Response(status=400)

        logs, name = args

        if not isinstance(logs, list):
            return Response(status=400)

        for row in logs:
            if len(row) != 2:
                continue

            level = row[0]
            msg = row[1]
            logger.log(level, f"[{name}@{request.access_route[0]}] {msg}")

        return Response(status=200)

    serve(app, port=SERVER_PORT)


if __name__ == "__main__":
    main()
