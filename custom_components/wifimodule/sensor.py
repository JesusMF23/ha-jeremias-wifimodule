"""Reported per-unit telemetry; invalid AQS values remain unknown."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfRatio, UnitOfTime

from .entity import UnitEntity


async def async_setup_entry(hass, entry, async_add_entities):
    items = []
    for unit in entry.runtime_data.data["units"]:
        for key in (
            "speed_level",
            "error_code",
            "filter_hours",
            "last_communication",
            "aqs1",
            "aqs2",
        ):
            items.append(Telemetry(entry.runtime_data, unit, key))
    async_add_entities(items)


class Telemetry(UnitEntity, SensorEntity):
    def __init__(self, c, unit, key):
        super().__init__(c, unit, key)
        self.key = key
        self.kind = None
        self._initialize_kind(unit["values"].get(key + "t"))
        if key in ("error_code", "last_communication"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if key == "filter_hours":
            self._attr_native_unit_of_measurement = UnitOfTime.HOURS

    def _initialize_kind(self, kind):
        # Once statistics have a unit, a later type change stays unknown until reload.
        if self.kind is not None or kind not in (1, 2, 3):
            return
        self.kind = kind
        if self.kind == 1:
            self._attr_native_unit_of_measurement = UnitOfRatio.PARTS_PER_MILLION
            self._attr_device_class = SensorDeviceClass.CO2
        elif self.kind == 2:
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_device_class = SensorDeviceClass.HUMIDITY
        elif self.kind == 3:
            self._attr_native_unit_of_measurement = "Bq/m³"
        if self.kind in (1, 2, 3):
            self._attr_state_class = SensorStateClass.MEASUREMENT

    def _handle_coordinator_update(self):
        if self.key.startswith("aqs"):
            self._initialize_kind(self.values.get(self.key + "t"))
        super()._handle_coordinator_update()

    @property
    def available(self):
        if self.key == "last_communication":
            return self.coordinator.last_update_success and bool(self.unit)
        return super().available

    @property
    def native_value(self):
        if self.key == "last_communication":
            return self.unit.get("last_comm")
        if self.key.startswith("aqs"):
            value = self.values.get(self.key)
            if (
                self.values.get(self.key + "t") != self.kind
                or self.kind not in (1, 2, 3)
                or value is None
                or value < 10
            ):
                return None
            return value / 10 if self.kind == 2 else value
        return self.values.get(
            {"speed_level": "spe", "error_code": "err", "filter_hours": "fil"}[self.key]
        )
