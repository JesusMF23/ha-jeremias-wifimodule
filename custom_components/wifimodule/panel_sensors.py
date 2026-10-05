"""Read-only sensor catalogue with the same freshness rules as regulation."""

from datetime import UTC, datetime

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .demand import KINDS, UNITS, Reading

CLASSES = {
    "co2": "carbon_dioxide",
    "tvoc": "volatile_organic_compounds_parts",
    "humidity": "humidity",
    "aqi": "aqi",
}


def sensor_catalogue(hass, max_age):
    """Use HA registry names; never infer zones from entity-id spelling."""
    candidates = {k: [] for k in KINDS}
    entities, devices = er.async_get(hass), dr.async_get(hass)
    now = datetime.now(UTC)
    for state in hass.states.async_all("sensor"):
        attrs = state.attributes
        for kind in KINDS:
            unit = attrs.get("unit_of_measurement")
            if attrs.get("device_class") != CLASSES[kind] or unit not in UNITS[kind]:
                continue
            age = (now - state.last_reported).total_seconds()
            reading = Reading(
                state.entity_id,
                state.name,
                kind,
                None if attrs.get("restored") else state.state,
                unit,
                age,
            )
            entry = entities.async_get(state.entity_id)
            device = (
                devices.async_get(entry.device_id)
                if entry and entry.device_id
                else None
            )
            candidates[kind].append(
                {
                    "entity_id": state.entity_id,
                    "name": state.name,
                    "device_id": device.id if device else None,
                    "zone_id": device.id if device else state.entity_id,
                    "zone": (device.name_by_user or device.name)
                    if device
                    else state.name,
                    "value": reading.numeric(max_age),
                    "unit": unit or "",
                    "age_seconds": round(max(0, age)),
                    "valid": reading.numeric(max_age) is not None,
                }
            )
    return candidates
