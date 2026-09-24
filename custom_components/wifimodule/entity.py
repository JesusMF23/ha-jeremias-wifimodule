"""Common group and per-unit entity registration."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class GroupEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.control = coordinator.controller
        self._attr_unique_id = f"{self.control.building_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self.control.building_id))},
            name=coordinator.data.get("name", "WifiModule"),
            manufacturer="WifiModule",
            model="Building control",
            configuration_url="https://wifimodule.eu/",
        )

    @property
    def available(self):
        return super().available and self.control.ready


class UnitEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, unit, key):
        super().__init__(coordinator)
        self.unit_id = unit["id"]
        self._attr_unique_id = (
            f"{coordinator.controller.building_id}_{unit['id']}_{key}"
        )
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"unit_{unit['id']}")},
            name=unit.get("name", "WifiModule"),
            manufacturer="WifiModule",
            model="Heat recovery ventilation",
            sw_version=unit.get("fw"),
        )

    @property
    def unit(self):
        return next(
            (u for u in self.coordinator.data["units"] if u["id"] == self.unit_id), {}
        )

    @property
    def values(self):
        return self.unit.get("values", {})

    @property
    def available(self):
        heartbeat = self.coordinator.controller.heartbeats.get(self.unit_id)
        return (
            super().available
            and bool(self.unit)
            and heartbeat is not None
            and heartbeat.fresh
        )
