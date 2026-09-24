"""Building-wide fan with native HA controls."""

import math

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.exceptions import HomeAssistantError

from .entity import GroupEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([Ventilation(entry.runtime_data)])


class Ventilation(GroupEntity, FanEntity):
    _attr_speed_count = 7
    _attr_preset_modes = ["schedule", "auto"]
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.PRESET_MODE
    )

    def __init__(self, coordinator):
        super().__init__(coordinator, "ventilation")

    @property
    def is_on(self):
        states = [u["values"].get("pwr") for u in self.coordinator.data["units"]]
        return (
            bool(any(states)) if states and all(s in (0, 1) for s in states) else None
        )

    @property
    def percentage(self):
        if self.is_on is False:
            return 0
        speeds = {u["values"].get("spe") for u in self.coordinator.data["units"]}
        if len(speeds) != 1:
            return None
        value = speeds.pop()
        return int(value * 100 / 7) if type(value) is int and 0 <= value <= 7 else None

    @property
    def preset_mode(self):
        data = self.coordinator.data
        if data.get("manual_active") is False:
            return "schedule"
        return "auto" if data.get("manual_mode") == "auto" else None

    @property
    def extra_state_attributes(self):
        return {
            "unit_count": len(self.coordinator.data["units"]),
            "manual_until": self.coordinator.data.get("manual_override_until"),
            "requested_speed": self.coordinator.data.get("manual_speed"),
        }

    async def async_set_percentage(self, percentage):
        if not 0 <= percentage <= 100:
            raise HomeAssistantError("Invalid percentage")
        await self.coordinator.command(
            self.control.control, speed=math.ceil(percentage * 7 / 100), mode="manual"
        )

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            await self.coordinator.command(self.control.control, speed=1, mode="manual")

    async def async_turn_off(self, **kwargs):
        await self.coordinator.command(self.control.control, speed=0, mode="manual")

    async def async_set_preset_mode(self, preset_mode):
        if preset_mode not in self.preset_modes:
            raise HomeAssistantError("Invalid preset")
        await self.coordinator.command(
            self.control.control,
            **({"schedule": True} if preset_mode == "schedule" else {"mode": "auto"}),
        )
