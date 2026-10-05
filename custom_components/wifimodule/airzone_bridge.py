"""Read live AirQ gases through the existing, optional Airzone Cloud session."""

import asyncio
import logging
from datetime import timedelta
from math import isfinite

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
FIELDS = {
    "co2": ("aq_co2", 250, 100000),
    "tvoc": ("aq_tvoc", 0, 1000000),
    "humidity": ("humidity", 0, 100),
}


def extract_values(status):
    """Never infer gases from the categorical AQI or reuse an earlier response."""
    if not isinstance(status, dict) or not all(
        status.get(flag) is True
        for flag in ("isConnected", "ws_connected", "aq_measuring")
    ):
        return {}
    values = {}
    for kind, (field, low, high) in FIELDS.items():
        raw = status.get(field)
        values[kind] = (
            raw
            if isinstance(raw, (int, float))
            and not isinstance(raw, bool)
            and isfinite(raw)
            and low <= raw <= high
            else None
        )
    return values


def _source_ready(entry, coordinator):
    return (
        entry.state is ConfigEntryState.LOADED
        and getattr(entry, "runtime_data", None) is coordinator
        and getattr(coordinator, "last_update_success", False)
    )


class AirQBridge(DataUpdateCoordinator):
    """One poller shared by all Jeremias entries; Airzone owns login and logout."""

    def __init__(self, hass):
        super().__init__(
            hass,
            _LOGGER,
            name="WifiModule AirQ readings",
            config_entry=None,
            update_interval=timedelta(seconds=60),
        )
        self.data = {}
        self.users = set()
        self._pending = set()
        self._poll_lock = asyncio.Lock()

    async def _read_device(self, entry, coordinator, device):
        device_id = device.get_id()
        zones = coordinator.data.get("zones", {}).values()
        names = sorted(
            {
                str(z["name"])
                for z in zones
                if z.get("air-quality-id") == device_id and z.get("name")
            }
        )
        row = {"name": "AirQ " + (", ".join(names) or device_id[-6:]), "values": {}}
        key = (entry.entry_id, device_id)
        if not _source_ready(entry, coordinator) or not device.data().get("available"):
            return key, row
        try:
            async with asyncio.timeout(15):
                status = await coordinator.airzone.api_get_device_status(device)
            if _source_ready(entry, coordinator) and device.data().get("available"):
                row["values"] = extract_values(status)
        except Exception:  # Third-party API errors must not take Jeremias offline.
            _LOGGER.debug("AirQ status request failed; measurements unavailable")
        return key, row

    async def _async_update_data(self):
        task = asyncio.current_task()
        self._pending.add(task)
        try:
            async with self._poll_lock:
                readings = {}
                sources = []
                for entry in self.hass.config_entries.async_entries("airzone_cloud"):
                    coordinator = getattr(entry, "runtime_data", None)
                    if coordinator is None or not _source_ready(entry, coordinator):
                        continue
                    client = getattr(coordinator, "airzone", None)
                    if not callable(getattr(client, "api_get_device_status", None)):
                        continue
                    # The existing client serializes its own HTTP requests.
                    source_rows = {}
                    for device in list(getattr(client, "air_quality", {}).values()):
                        key, row = await self._read_device(entry, coordinator, device)
                        source_rows[key] = row
                    readings.update(source_rows)
                    sources.append((entry, coordinator, source_rows))
                # Another GET may have yielded while a previous source unloaded.
                for entry, coordinator, rows in sources:
                    if not _source_ready(entry, coordinator):
                        for row in rows.values():
                            row["values"] = {}
                return readings
        finally:
            self._pending.discard(task)

    async def async_shutdown(self):
        await super().async_shutdown()
        tasks = self._pending - {asyncio.current_task()}
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


async def async_acquire_bridge(hass, entry):
    data = hass.data[DOMAIN]
    if (bridge := data.get("airq_bridge")) is None:
        bridge = data["airq_bridge"] = AirQBridge(hass)
        await bridge.async_register_shutdown()
    bridge.users.add(entry.entry_id)
    return bridge


async def async_release_bridge(hass, entry):
    data = hass.data[DOMAIN]
    if (bridge := data.get("airq_bridge")) is not None:
        bridge.users.discard(entry.entry_id)
        if not bridge.users:
            # Remove before awaiting so a new entry cannot acquire a closing bridge.
            data.pop("airq_bridge")
            await bridge.async_shutdown()
