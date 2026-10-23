"""Wiedergabe mit absoluten Deadlines (kein Drift), Pause/Resume/Stop und Keepalive."""
import asyncio
import time

KEEPALIVE_S = 10.0


class Player:
    def __init__(self, set_fn, on_event):
        self.set_fn = set_fn          # async (lat, lon)
        self.on_event = on_event      # async (dict)
        self.state = "idle"
        self._task = None
        self._run = asyncio.Event()
        self._stop = False

    async def start(self, steps):
        await self.stop()
        self._stop = False
        self._run.set()
        self.state = "playing"
        self._task = asyncio.create_task(self._loop(steps))

    async def pause(self):
        if self.state == "playing":
            self._run.clear()
            self.state = "paused"
            await self.on_event({"type": "state", "state": self.state})

    async def resume(self):
        if self.state == "paused":
            self._run.set()
            self.state = "playing"
            await self.on_event({"type": "state", "state": self.state})

    async def stop(self):
        if self._task and not self._task.done():
            self._stop = True
            self._run.set()
            await self._task
        self.state = "idle"
        await self.on_event({"type": "state", "state": self.state})

    async def _loop(self, steps):
        total = sum(s.hold_s for s in steps)
        done = 0.0
        next_t = time.monotonic()
        try:
            for s in steps:
                await self.set_fn(s.lat, s.lon)
                last_set = time.monotonic()
                next_t += s.hold_s
                await self.on_event({"type": "pos", "lat": s.lat, "lon": s.lon,
                                     "hold_s": s.hold_s, "progress": done / total if total else 1})
                while not self._stop:
                    if not self._run.is_set():
                        t0 = time.monotonic()
                        await self._run.wait()
                        next_t += time.monotonic() - t0   # Pausenzeit verschiebt die Deadline
                        continue
                    rem = next_t - time.monotonic()
                    if rem <= 0:
                        break
                    await asyncio.sleep(min(rem, 0.25))
                    if time.monotonic() - last_set >= KEEPALIVE_S and next_t - time.monotonic() > 0.5:
                        await self.set_fn(s.lat, s.lon)
                        last_set = time.monotonic()
                if self._stop:
                    return
                done += s.hold_s
        finally:
            self.state = "idle"
            await self.on_event({"type": "state", "state": "idle"})
