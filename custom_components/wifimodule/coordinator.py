"""Shared cloud polling and entity command errors."""

import logging
from datetime import UTC, datetime, timedelta
from time import monotonic

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ApiError, AuthError, ControlCancelled
from .const import DOMAIN, POLL_SECONDS
from .models import integer, override_expiry


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
        self.automatic = None
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
        generation = None
        return_to = kwargs.pop("return_to", "none")
        expires_at = None
        if return_to not in ("none", "automatic", "schedule"):
            raise HomeAssistantError("Invalid return destination")
        a = self.automatic
        bypass_only = method == self.controller.control and set(kwargs) == {"bypass"}
        if bypass_only and a is not None and a.enabled:
            return await a.set_bypass(kwargs["bypass"])
        if bypass_only and a is not None and a.manual_control.active:
            return_to = a.manual_control.return_to
            expires_at = a.manual_control.expires_at
            kwargs["speed"] = a.manual_control.speed
        if return_to != "none" and expires_at is None:
            if (
                method != self.controller.control
                or kwargs.get("schedule")
                or kwargs.get("speed") == 8
                or kwargs.get("mode") == "auto"
            ):
                raise HomeAssistantError("Timed return requires manual speed 0–7")
            minutes = integer(kwargs.get("duration"), 1, 10080)
            if return_to == "automatic" and (a is None or not any(a.sensors.values())):
                raise HomeAssistantError("Select sensors before returning to Automatic")
            end = datetime.now(UTC) + timedelta(minutes=minutes)
            if return_to == "schedule":
                end = end.replace(second=0, microsecond=0)
                override_expiry(end, self.controller.timezone)
            expires_at = end.isoformat()
        if expires_at and datetime.fromisoformat(expires_at) <= datetime.now(UTC):
            raise HomeAssistantError(
                "Timer expired; wait for the return before changing bypass"
            )
        if self.automatic is not None and method in (
            self.controller.control,
            self.controller.activate,
        ):
            await self.automatic.manual()
            generation = self.automatic.generation
        if method == self.controller.control:
            if (
                not kwargs.get("schedule")
                and kwargs.get("speed") != 8
                and kwargs.get("mode") != "auto"
            ):
                kwargs.update(duration=0, mode="manual")
                if return_to == "schedule":
                    kwargs["_expires_at"] = expires_at
            if generation is not None:
                kwargs["_guard"] = lambda: (
                    not self.automatic._closed
                    and generation == self.automatic.generation
                    and not self.automatic.enabled
                )
        try:
            result = await method(*args, **kwargs)
        except AuthError:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="auth_required"
            ) from None
        except ControlCancelled:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="control_superseded"
            ) from None
        except ApiError:
            if generation is not None and generation == self.automatic.generation:
                await self.automatic.manual("command_error")
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from None
        if generation is not None and generation == self.automatic.generation:
            if method == self.controller.control:
                payload = self.controller.last_control
                if type(payload.get("bypass")) is bool:
                    self.automatic.bypass_requested = payload["bypass"]
                self.automatic.manual_control.record(
                    self.controller.last_control,
                    monotonic(),
                    return_to=return_to,
                    expires_at=expires_at,
                )
            elif method == self.controller.activate:
                self.automatic.status = "schedule"
                self.automatic._persist()
        self._metadata_at = 0
        await self.async_request_refresh()
        return result
