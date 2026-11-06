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
                # Refresh static data if empty (startup fetch failed) or if
                # an arrival references a route we don't know about.
                if not route_map or any(a.get("route_code") not in route_map for a in raw):
                    try:
                        route_map = build_route_map(STOP_CODE) or route_map
                    except Exception as e:
                        print(f"route map refresh failed: {e}", flush=True)
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
        elif self.path == "/static/nosleep.mp4":
            self._serve_file("static/nosleep.mp4", "video/mp4")
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
            size = os.path.getsize(path)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            return

        # iOS Safari requires 206 Partial Content responses to Range requests
        # before it will play a video element.
        range_header = self.headers.get("Range", "")
        start, end = 0, size - 1
        partial = False
        if range_header.startswith("bytes="):
            spec = range_header[6:].split(",", 1)[0].strip()
            lo, _, hi = spec.partition("-")
            try:
                if lo:
                    start = int(lo)
                    end = int(hi) if hi else size - 1
                else:
                    start = size - int(hi)
                    end = size - 1
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            if start < 0 or start >= size or end >= size or start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            partial = True

        length = end - start + 1
        with open(path, "rb") as f:
            f.seek(start)
            data = f.read(length)

        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    poller = threading.Thread(target=poll_loop, daemon=True)
    poller.start()

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Serving on http://{HOST}:{PORT}  (stop {STOP_CODE})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
