#!/usr/bin/env python3
"""
OASA bus arrival display server.
Polls the OASA Telematics API every 60 seconds and serves a fullscreen
LED-matrix-style arrival board at http://<pi-ip>:8080
"""

import gzip
import json
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STOP_CODE = "060502"
POLL_INTERVAL = 60  # seconds between OASA API polls
PORT = 8888
HOST = "127.0.0.1"  # only nginx should reach this directly
API_BASE = "https://telematics.oasa.gr/api/"

# Shared state updated by the poller thread
state_lock = threading.Lock()
state = {
    "arrivals": [],
    "stop_name": "",
    "updated_at": None,
    "error": None,
}


def oasa_get(act, p1=""):
    url = f"{API_BASE}?act={act}&p1={p1}"
    req = urllib.request.Request(url, headers={"User-Agent": "oasa-display/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read()
    try:
        body = gzip.decompress(body)
    except OSError:
        pass
    return json.loads(body.decode("utf-8"))


def build_route_map(stop_code):
    """Returns {route_code: {line_id, line_descr, route_descr}} for a stop."""
    routes = oasa_get("webRoutesForStop", stop_code)
    result = {}
    if not routes:
        return result
    for r in routes:
        result[r["RouteCode"]] = {
            "line_id": r["LineID"],
            "line_descr": r["LineDescr"],
            "route_descr": r["RouteDescr"],
        }
    return result


def fetch_stop_name(stop_code):
    data = oasa_get("getStopNameAndXY", stop_code)
    if data and isinstance(data, list):
        return data[0].get("stop_descr", stop_code)
    return stop_code


def poll_loop():
    global state

    # Fetch static data once
    try:
        stop_name = fetch_stop_name(STOP_CODE)
        route_map = build_route_map(STOP_CODE)
    except Exception as e:
        with state_lock:
            state["error"] = f"Startup error: {e}"
        stop_name = STOP_CODE
        route_map = {}

    with state_lock:
        state["stop_name"] = stop_name

    while True:
        try:
            raw = oasa_get("getStopArrivals", STOP_CODE)
            arrivals = []
            if raw:
                for a in raw:
                    rc = a.get("route_code", "")
                    info = route_map.get(rc, {})
                    arrivals.append({
                        "line_id": info.get("line_id", rc),
                        "destination": info.get("route_descr", ""),
                        "minutes": int(a.get("btime2", 0)),
                    })
            arrivals.sort(key=lambda x: x["minutes"])
            with state_lock:
                state["arrivals"] = arrivals
                state["updated_at"] = time.strftime("%H:%M")
                state["error"] = None
        except Exception as e:
            with state_lock:
                state["error"] = str(e)

        time.sleep(POLL_INTERVAL)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence request logs

    def do_GET(self):
        if self.path == "/api/arrivals":
            self._serve_json()
        elif self.path in ("/", "/index.html"):
            self._serve_file("display.html", "text/html; charset=utf-8")
        elif self.path == "/static/VT323.woff2":
            self._serve_file("static/VT323.woff2", "font/woff2")
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_json(self):
        with state_lock:
            payload = json.dumps(state).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _serve_file(self, filename, content_type):
        path = os.path.join(os.path.dirname(__file__), filename)
        try:
            with open(path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    poller = threading.Thread(target=poll_loop, daemon=True)
    poller.start()

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Serving on http://{HOST}:{PORT}  (stop {STOP_CODE})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
