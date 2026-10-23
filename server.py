import asyncio
import os

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from device import Device
from player import Player
from route import build_steps, geocode, route_all

app = FastAPI()
device = Device(dry_run=os.getenv("DRY_RUN") == "1")
clients: set[WebSocket] = set()


async def broadcast(msg: dict):
    for c in list(clients):
        try:
            await c.send_json(msg)
        except Exception:  # noqa: BLE001
            clients.discard(c)


async def set_pos(lat, lon):
    await asyncio.to_thread(device.set, lat, lon)


player = Player(set_pos, broadcast)


class WP(BaseModel):
    lat: float
    lon: float
    dwell_min: float = 0


class RouteReq(BaseModel):
    waypoints: list[WP]
    profile: str = "foot"
    speed_kmh: float = 5.0


@app.on_event("startup")
async def _startup():
    try:
        await asyncio.to_thread(device.connect)
    except Exception as e:  # noqa: BLE001
        print("WARNUNG:", e, "\nTipp: DRY_RUN=1 zum Testen ohne Geraet.")


@app.get("/api/status")
async def status():
    return {"device": device.kind, "state": player.state}


@app.get("/api/geocode")
async def api_geocode(q: str):
    return await geocode(q)


async def _route(req: RouteReq):
    if len(req.waypoints) < 2:
        raise HTTPException(400, "Mindestens Start und Ziel noetig")
    pts = [(w.lat, w.lon) for w in req.waypoints]
    try:
        return await route_all(req.profile, pts)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Routing fehlgeschlagen: {e}")


@app.post("/api/route")
async def api_route(req: RouteReq):
    legs, dist, dur = await _route(req)
    return {"legs": legs, "distance_m": dist,
            "sim_duration_s": dist / (req.speed_kmh / 3.6)
            + sum(w.dwell_min for w in req.waypoints) * 60}


@app.post("/api/play")
async def api_play(req: RouteReq):
    if device.kind is None:
        raise HTTPException(503, "Kein Geraet verbunden")
    legs, _, _ = await _route(req)
    steps = build_steps(legs, [w.dwell_min * 60 for w in req.waypoints], req.speed_kmh / 3.6)
    await player.start(steps)
    return {"steps": len(steps)}


class Pt(BaseModel):
    lat: float
    lon: float


@app.post("/api/teleport")
async def teleport(p: Pt):
    await player.stop()
    await set_pos(p.lat, p.lon)
    await broadcast({"type": "pos", "lat": p.lat, "lon": p.lon, "hold_s": 0, "progress": 0})


@app.post("/api/pause")
async def pause():
    await player.pause()


@app.post("/api/resume")
async def resume():
    await player.resume()


@app.post("/api/stop")
async def stop():
    await player.stop()


@app.post("/api/reset")
async def reset():
    await player.stop()
    await asyncio.to_thread(device.clear)


@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    clients.add(sock)
    try:
        while True:
            await sock.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(sock)


@app.get("/")
async def index():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
