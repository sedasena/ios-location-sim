"""Geraeteanbindung: iOS 17+ ueber tunneld/DVT, iOS <= 16 ueber Lockdown, oder Dry-Run ohne Geraet."""
import logging

log = logging.getLogger("device")


class Device:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.kind = None
        self._sim = None
        self._dvt = None

    def connect(self):
        if self.dry_run:
            self.kind = "dry-run"
            return
        try:
            from pymobiledevice3.tunneld.api import get_tunneld_devices
            from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
            from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
            rsds = get_tunneld_devices()
            if rsds:
                self._dvt = DvtProvider(rsds[0])
                self._dvt.__enter__()
                self._sim = LocationSimulation(self._dvt)
                self.kind = "ios17+ (DVT)"
                return
        except Exception as e:  # noqa: BLE001
            log.warning("DVT-Weg fehlgeschlagen: %s", e)
        try:
            from pymobiledevice3.lockdown import create_using_usbmux
            from pymobiledevice3.services.simulate_location import DtSimulateLocation
            self._sim = DtSimulateLocation(create_using_usbmux())
            self.kind = "legacy (Lockdown)"
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(
                "Kein Geraet erreichbar. Laeuft tunneld (sudo)? Developer Mode an? DDI gemountet? "
                f"Details: {e}"
            ) from e

    def set(self, lat: float, lon: float):
        if self.dry_run:
            return
        try:
            self._sim.set(lat, lon)
        except Exception:  # einmal neu verbinden
            self.connect()
            self._sim.set(lat, lon)

    def clear(self):
        if not self.dry_run and self._sim:
            self._sim.clear()

    def close(self):
        try:
            self.clear()
            if self._dvt:
                self._dvt.__exit__(None, None, None)
        except Exception:  # noqa: BLE001
            pass
