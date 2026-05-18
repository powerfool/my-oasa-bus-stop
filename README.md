# My OASA Bus Stop

My girlfriend takes the same bus each morning to work. As she gets ready, she has to check the OASA Telematics app on her phone every few minutes to see when the bus will come. Using the [OASA Telematics](https://telematics.oasa.gr) API I've created this simple service to run on our Raspberry Pi so we can use an old phone in our kitchen to have a permament display of the bus stop arrival times. 

<img width="166" height="300" alt="OASA Display" src="https://github.com/user-attachments/assets/36d98718-fdb5-4d45-b397-446935661df3" />



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

## OASA API

Base URL: `https://telematics.oasa.gr/api/`

| Action | Parameter | Returns |
|--------|-----------|---------|
| `getStopArrivals` | `p1=stop_code` | Upcoming buses — `{route_code, btime2}` where `btime2` is minutes as a string. Returns `null` when no buses. |
| `webRoutesForStop` | `p1=stop_code` | Routes serving the stop — `RouteCode`, `LineID` (e.g. "224"), `RouteDescr` |
| `getStopNameAndXY` | `p1=stop_code` | Stop name and coordinates |

No authentication required.
