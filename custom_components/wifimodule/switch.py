"""Explicit manual bypass request."""

from homeassistant.components.switch import SwitchEntity

from .entity import GroupEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([Bypass(entry.runtime_data)])


class Bypass(GroupEntity, SwitchEntity):
    def __init__(self, c):
        super().__init__(c, "bypass")

    @property
    def is_on(self):
        values = {u["values"].get("byp") for u in self.coordinator.data["units"]}
        if len(values) != 1:
            return None
        value = values.pop()
        return bool(value) if value in (0, 1) else None

    async def async_turn_on(self, **kwargs):
        await self.coordinator.command(self.control.control, bypass=True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.command(self.control.control, bypass=False)
