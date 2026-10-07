"""Read-only sensor catalogue with the same freshness rules as regulation."""

from datetime import UTC, datetime

from homeassistant.helpers import area_registry as ar
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
            device_class = attrs.get("device_class")
            matches_class = device_class == CLASSES[kind] or (
                kind == "tvoc" and device_class == "volatile_organic_compounds"
            )
            if not matches_class and not (
                device_class is None and unit in UNITS[kind] and unit not in (None, "")
            ):
                continue
            compatible = unit in UNITS[kind]
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
            area_id = getattr(entry, "area_id", None) or getattr(
                device, "area_id", None
            )
            area = (
                ar.async_get(hass).async_get_area(area_id)
                if isinstance(area_id, str)
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
                    "compatible": compatible,
                    "reason": None if compatible else "incompatible_unit",
                    "area": area.name if area else None,
                    "unclassified": device_class is None,
                    "source_unit": unit or "",
                    "value": reading.numeric(max_age),
                    "unit": "ppb" if kind == "tvoc" and compatible else unit or "",
                    "age_seconds": round(max(0, age)),
                    "valid": reading.numeric(max_age) is not None,
                }
            )
    return candidates
