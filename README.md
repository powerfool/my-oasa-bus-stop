# My OASA Bus Stop

My girlfriend takes the same bus each morning to work. As she gets ready, she has to check the OASA Telematics app on her phone every few minutes to see when the bus will come. Using the [OASA Telematics](https://telematics.oasa.gr) API I've created this simple service to run on our Raspberry Pi so we can use an old phone in our kitchen to have a permament display of the bus stop arrival times. 

<img width="166" height="300" alt="OASA Display" src="https://github.com/user-attachments/assets/36d98718-fdb5-4d45-b397-446935661df3" />



## How it works

`server.py` runs two things concurrently:

- **Poller thread** — fetches arrivals for every configured stop from the OASA API every 60 seconds and stores the result in a shared state dict
- **HTTP server** — serves `display.html` and a `/api/arrivals` JSON endpoint on `127.0.0.1:8888`

The browser polls `/api/arrivals` every 30 seconds and redraws the board in place. Each stop gets its own labelled section, and the layout scales to fit the screen however many buses are showing, so it never needs scrolling. No frameworks, no build step, no external dependencies — the VT323 font is self-hosted.

## Configuration

Open `server.py` and change the constants at the top:

```python
STOP_CODES = ["060502", "060545", "060642"]  # OASA stop codes, shown top to bottom
PORT       = 8888
```

Add as many stops as will fit legibly on your screen. To find a stop code, look it up on [telematics.oasa.gr](https://telematics.oasa.gr) or use the `getStopNameAndXY` API action.

## Running locally

```bash
python3 server.py
# open http://localhost:8888
```

No dependencies beyond the Python standard library.

## OASA API

Base URL: `https://telematics.oasa.gr/api/`

| Action | Parameter | Returns |
|--------|-----------|---------|
| `getStopArrivals` | `p1=stop_code` | Upcoming buses — `{route_code, btime2}` where `btime2` is minutes as a string. Returns `null` when no buses. |
| `webRoutesForStop` | `p1=stop_code` | Routes serving the stop — `RouteCode`, `LineID` (e.g. "224"), `RouteDescr` |
| `getStopNameAndXY` | `p1=stop_code` | Stop name and coordinates |

No authentication required.

`/api/arrivals` returns `{"stops": [{"code", "name", "arrivals": [{"line_id", "destination", "minutes"}], "error"}], "updated_at", "error"}`.
