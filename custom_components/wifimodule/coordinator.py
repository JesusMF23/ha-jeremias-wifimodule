"""Shared cloud polling and entity command errors."""

import logging
from datetime import timedelta
from time import monotonic

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ApiError, AuthError
from .const import DOMAIN, POLL_SECONDS


class Coordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, controller):
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=POLL_SECONDS),
        )
        self.controller = controller
        self.profiles = []
        self._metadata_at = 0

    async def _async_update_data(self):
        try:
            async with self.controller.lock:
                data = await self.controller.poll()
                if not self.profiles or monotonic() - self._metadata_at > 300:
                    self.profiles = await self.controller.profiles()
                    self._metadata_at = monotonic()
                return data
        except AuthError:
            raise ConfigEntryAuthFailed("WifiModule authentication required") from None
        except ApiError:
            raise UpdateFailed("WifiModule cloud data unavailable") from None

    async def command(self, method, *args, **kwargs):
        try:
            result = await method(*args, **kwargs)
        except AuthError:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="auth_required"
            ) from None
        except ApiError:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from None
        self._metadata_at = 0
        await self.async_request_refresh()
        return result
