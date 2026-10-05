"""Local controls remain available while the manufacturer's cloud is offline."""

from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .entity import GroupEntity


class AutomaticEntity(GroupEntity):
    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self.automatic = coordinator.automatic

    @property
    def available(self):
        return True

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.automatic.signal, self.async_write_ha_state
            )
        )
