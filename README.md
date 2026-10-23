# iOS Location Sim

## Setup
    pip install -r requirements.txt
    # iOS 17+: developer mode on, then:
    pymobiledevice3 mounter auto-mount
    sudo python3 -m pymobiledevice3 remote tunneld # terminal stays open

## Start
    uvicorn server:app --port 8000
    # test without device:  DRY_RUN=1 uvicorn server:app --port 8000
Then open http://localhost:8000.

## How to use
Search for an address or click on the map (start, stops, destination), enter the duration in minutes for each point,
select “Profile + Speed,” click “Calculate Route,” and then click “Start.”

## Notes
- Lock in the “pymobiledevice3” version; the API changes in some respects (synchronous/asynchronous). Adjust the imports in “device.py” as needed.
- The backend must be running as long as the simulation is running (the simulation relies on the DVT connection).
- Nominatim and routing.openstreetmap.de are public services with fair-use rules: Do not send an excessive number of requests.
  For continuous operation, host OSRM/Nominatim yourself (to do this, simply change the URLs in route.py).

