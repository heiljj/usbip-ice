from flask import Flask, request, Response, jsonify
import os
import psycopg
from waitress import serve
import logging
import sys

from control.ControlDatabase import ControlDatabase
from utils.NotificationSender import NotificationSender

def expect_json(parms, fun):
    if request.content_type != "application/json":
        return Response(status=400)
    try:
        json = request.get_json()
    except Exception:
        return Response(status=400)
    
    args = []

    for p in parms:
        value = json.get(p)
        if not value:
            return Response(status=400)
        args.append(value)
    
    if len(args) != len(parms):
        return Response(status=400)
    
    return fun(*args)

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
    
    database = ControlDatabase(DATABASE_URL)
    notif = NotificationSender(DATABASE_URL, logger)
    app = Flask(__name__)

    @app.get("/reserve")
    def make_reservations():
        return jsonify(expect_json(["amount", "url", "name"], database.reserve))

    @app.get("/extend")
    def extend():
        return jsonify(expect_json(["name", "serials"], database.extend))

    @app.get("/extendall")
    def extendall():
        return jsonify(expect_json(["name"], database.extendAll))

    @app.get("/end")
    def end():
        data = expect_json(["name", "serials"], database.end)

        if not data:
            return jsonify({})

        for row in data:
            notif.sendDeviceDisconnect(row["serial"])
            notif.sendWorkerUnreserve(row["serial"])
        
        return jsonify(list(map(lambda x : x["serial"], data)))

    @app.get("/endall")
    def endall():
        data = expect_json(["name"], database.endAll)

        if not data:
            return jsonify({})

        for row in data:
            notif.sendDeviceDisconnect(row["serial"])
            notif.sendWorkerUnreserve(row["serial"])
            
        
        return jsonify(list(map(lambda x : x["serial"], data)))
    
    serve(app, port=SERVER_PORT)

if __name__ == "__main__":
    main()