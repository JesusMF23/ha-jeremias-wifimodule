"""Bounded boost and return to schedule."""

from homeassistant.components.button import ButtonEntity

from .entity import GroupEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [Command(entry.runtime_data, key) for key in ("boost", "resume_schedule")]
    )


class Command(GroupEntity, ButtonEntity):
    def __init__(self, c, key):
        super().__init__(c, key)
        self.key = key

    async def async_press(self):
        await self.coordinator.command(
            self.control.control,
            **(
                {"speed": 8, "duration": 5, "mode": "manual"}
                if self.key == "boost"
                else {"schedule": True}
            ),
        )
