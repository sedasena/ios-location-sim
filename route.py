"""Geo-Mathe, Routing (OSRM) und Geocoding (Nominatim)."""
import math
from dataclasses import dataclass

import httpx

R = 6_371_008.8
UA = {"User-Agent": "ios-location-sim/0.1 (private dev tool)"}
PROFILES = {"foot": "routed-foot", "bike": "routed-bike", "car": "routed-car"}


@dataclass
class Step:
    lat: float
    lon: float
    hold_s: float


def haversine(a, b) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(h))


def lerp(a, b, f):
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


def resample(poly, step_m):
    """Punkte im festen Abstand step_m entlang der Polyline (Rest wird ueber Eckpunkte mitgefuehrt)."""
    need = step_m
    yield poly[0]
    for a, b in zip(poly, poly[1:]):
        seg = haversine(a, b)
        if seg == 0:
            continue
        d = 0.0
        while seg - d >= need:
            d += need
            yield lerp(a, b, d / seg)
            need = step_m
        need -= seg - d
    yield poly[-1]


def build_steps(legs, dwell_s, speed_mps, dt=1.0):
    """legs: Liste von Polylines [(lat,lon),...]; dwell_s: Verweildauer je Wegpunkt (len = len(legs)+1)."""
    steps = []
    start = legs[0][0]
    steps.append(Step(*start, dwell_s[0] if dwell_s[0] > 0 else dt))
    for i, leg in enumerate(legs):
        pts = list(resample(leg, speed_mps * dt))
        steps += [Step(lat, lon, dt) for lat, lon in pts[1:]]
        if dwell_s[i + 1] > 0:
            end = leg[-1]
            steps.append(Step(end[0], end[1], dwell_s[i + 1]))  # EIN Step statt tausender Duplikate
    return steps


async def geocode(q: str):
    async with httpx.AsyncClient(headers=UA, timeout=10) as c:
        r = await c.get("https://nominatim.openstreetmap.org/search",
                        params={"q": q, "format": "jsonv2", "limit": 6})
        r.raise_for_status()
        return [{"label": x["display_name"], "lat": float(x["lat"]), "lon": float(x["lon"])}
                for x in r.json()]


async def route_leg(client, profile, a, b):
    url = (f"https://routing.openstreetmap.de/{PROFILES[profile]}/route/v1/driving/"
           f"{a[1]},{a[0]};{b[1]},{b[0]}")
    r = await client.get(url, params={"overview": "full", "geometries": "geojson"})
    r.raise_for_status()
    data = r.json()
    if not data.get("routes"):
        raise ValueError("Keine Route gefunden")
    rt = data["routes"][0]
    poly = [(lat, lon) for lon, lat in rt["geometry"]["coordinates"]]
    return poly, rt["distance"], rt["duration"]


async def route_all(profile, points):
    legs, dist, dur = [], 0.0, 0.0
    async with httpx.AsyncClient(headers=UA, timeout=20) as c:
        for a, b in zip(points, points[1:]):
            poly, d, t = await route_leg(c, profile, a, b)
            legs.append(poly)
            dist += d
            dur += t
    return legs, dist, dur
