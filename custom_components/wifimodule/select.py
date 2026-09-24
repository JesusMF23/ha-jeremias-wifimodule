"""Native control mode and active profile selectors."""

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError

from .entity import GroupEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([Mode(entry.runtime_data), Profile(entry.runtime_data)])


class Mode(GroupEntity, SelectEntity):
    _attr_options = ["schedule", "manual", "auto"]

    def __init__(self, c):
        super().__init__(c, "control_mode")

    @property
    def current_option(self):
        return (
            "schedule"
            if self.coordinator.data.get("manual_active") is False
            else self.coordinator.data.get("manual_mode")
        )

    async def async_select_option(self, option):
        if option not in self.options:
            raise HomeAssistantError("Invalid mode")
        await self.coordinator.command(
            self.control.control,
            **({"schedule": True} if option == "schedule" else {"mode": option}),
        )


class Profile(GroupEntity, SelectEntity):
    def __init__(self, c):
        super().__init__(c, "profile")

    @property
    def options(self):
        return [f"{p['name']} [{p['id']}]" for p in self.coordinator.profiles]

    @property
    def current_option(self):
        return next(
            (
                f"{p['name']} [{p['id']}]"
                for p in self.coordinator.profiles
                if p["id"] == self.coordinator.data.get("profile_id")
            ),
            None,
        )

    async def async_select_option(self, option):
        if option not in self.options:
            raise HomeAssistantError("Unknown profile")
        index = self.options.index(option)
        await self.coordinator.command(
            self.control.activate, self.coordinator.profiles[index]["id"]
        )
