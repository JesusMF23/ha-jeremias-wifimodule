"""Local default duration for future manual commands."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime

from .entity import GroupEntity
from .models import integer


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([Duration(entry.runtime_data)])


class Duration(GroupEntity, NumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 10080
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, c):
        super().__init__(c, "override_duration")

    @property
    def available(self):
        return True

    @property
    def native_value(self):
        return self.control.duration

    async def async_set_native_value(self, value):
        if not float(value).is_integer():
            raise ValueError("Whole minutes required")
        self.control.duration = integer(int(value), 0, 10080)
        entry = self.coordinator.config_entry
        self.hass.config_entries.async_update_entry(
            entry, options={**entry.options, "duration": self.control.duration}
        )
        self.async_write_ha_state()
