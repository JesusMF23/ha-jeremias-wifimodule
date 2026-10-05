"""Native AirQ readings sourced by the read-only shared Airzone adapter."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfRatio
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

KINDS = {
    "co2": (SensorDeviceClass.CO2, UnitOfRatio.PARTS_PER_MILLION),
    "tvoc": (
        SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        UnitOfRatio.PARTS_PER_BILLION,
    ),
    "humidity": (SensorDeviceClass.HUMIDITY, PERCENTAGE),
}


async def async_setup_airq(entry, async_add_entities):
    bridge = entry.runtime_data.airq
    known = set()

    @callback
    def discover():
        added = []
        for key in bridge.data or {}:
            if key not in known:
                known.add(key)
                added.extend(
                    AirQSensor(bridge, key, kind, entry.data["building_id"])
                    for kind in KINDS
                )
        if added:
            async_add_entities(added)

    # Keep discovery running even when Airzone loads after Jeremias or is offline.
    entry.async_on_unload(bridge.async_add_listener(discover))
    await bridge.async_request_refresh()
    discover()


class AirQSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, bridge, key, kind, building_id=1):
        super().__init__(bridge)
        self.key, self.kind = key, kind
        device_id = f"airq_{building_id}_{key[0]}_{key[1]}"
        self._attr_unique_id = f"{device_id}_{kind}"
        self._attr_translation_key = f"airq_{kind}"
        self._attr_device_class, self._attr_native_unit_of_measurement = KINDS[kind]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=bridge.data[key]["name"],
            manufacturer="Airzone",
            model="AirQ",
        )

    @property
    def available(self):
        return super().available and self.native_value is not None

    @property
    def native_value(self):
        return (
            (self.coordinator.data or {})
            .get(self.key, {})
            .get("values", {})
            .get(self.kind)
        )
