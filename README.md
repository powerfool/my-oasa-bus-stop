# My OASA Bus Stop

A real-time Athens bus arrival display for a Raspberry Pi. Polls the [OASA Telematics](https://telematics.oasa.gr) API and serves a fullscreen arrival board designed to sit on a phone or tablet in the kitchen.

![Amber LED-style arrival board](.github/preview.png)

## What it looks like

Black background, amber text, dot-matrix VT323 font, CRT scanline overlay. Landscape mode shows a classic three-column departure board (line · destination · minutes). Portrait mode stacks each arrival as a card with the countdown in large type at the bottom.

When a bus is ≤1 minute away the row turns white and shows **ΤΩΡΑ** (now).

## How it works

`server.py` runs two things concurrently:

- **Poller thread** — fetches arrivals from the OASA API every 60 seconds and stores the result in a shared state dict
- **HTTP server** — serves `display.html` and a `/api/arrivals` JSON endpoint on `127.0.0.1:8888`

The browser polls `/api/arrivals` every 30 seconds and updates the DOM in place. No frameworks, no build step, no external dependencies — the VT323 font is self-hosted.

## Configuration

Open `server.py` and change the constants at the top:

```python
STOP_CODE = "060502"   # OASA stop code — find yours via the API or the OASA app
PORT      = 8888
```

To find your stop code, look it up on [telematics.oasa.gr](https://telematics.oasa.gr) or use the `getStopNameAndXY` API action.

## Running locally

```bash
python3 server.py
# open http://localhost:8888
```

No dependencies beyond the Python standard library.

## Running on a Raspberry Pi (systemd + nginx)

Create `/etc/systemd/system/oasa-display.service`:

```ini
[Unit]
Description=OASA Bus Display
After=network-online.target
Wants=network-online.target

[Service]
User=dimitris
WorkingDirectory=/home/dimitris/oasa
ExecStart=/usr/bin/python3 /home/dimitris/oasa/server.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable --now oasa-display
```

Then proxy it through nginx so it's reachable by IP on port 80:

```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    location / {
        proxy_pass http://127.0.0.1:8888;
    }
}
```

## OASA API

Base URL: `https://telematics.oasa.gr/api/`

| Action | Parameter | Returns |
|--------|-----------|---------|
| `getStopArrivals` | `p1=stop_code` | Upcoming buses — `{route_code, btime2}` where `btime2` is minutes as a string. Returns `null` when no buses. |
| `webRoutesForStop` | `p1=stop_code` | Routes serving the stop — `RouteCode`, `LineID` (e.g. "224"), `RouteDescr` |
| `getStopNameAndXY` | `p1=stop_code` | Stop name and coordinates |

No authentication required.

## License

MIT
