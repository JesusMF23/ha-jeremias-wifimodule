"""Physical flags, independent from command acknowledgement."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .entity import UnitEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            Flag(entry.runtime_data, u, k)
            for u in entry.runtime_data.data["units"]
            for k in ("power", "boost_active", "bypass_active", "problem")
        ]
    )


class Flag(UnitEntity, BinarySensorEntity):
    def __init__(self, c, unit, key):
        super().__init__(c, unit, key)
        self.key = key
        if key == "problem":
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        if key == "power":
            self._attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self):
        value = self.values.get(
            {
                "power": "pwr",
                "boost_active": "bst",
                "bypass_active": "byp",
                "problem": "err",
            }[self.key]
        )
        if value is None:
            return None
        if self.key == "problem":
            return value != 0
        return bool(value) if value in (0, 1) else None
