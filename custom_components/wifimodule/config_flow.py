"""Discover buildings after sign-in; no installation-specific defaults."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import voluptuous as vol
from aiohttp import CookieJar
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import ApiError, AuthError, DeviceError, WifiModuleApi
from .const import DOMAIN
from .models import normalize_building, record

CREDENTIALS = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL)
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class WifiModuleConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self):
        self._credentials = {}
        self._buildings = []
        self._status = []

    async def _discover(self, credentials):
        session = async_create_clientsession(
            self.hass, cookie_jar=CookieJar(), auto_cleanup=False
        )
        try:
            api = WifiModuleApi(
                session, credentials[CONF_USERNAME], credentials[CONF_PASSWORD]
            )
            self._status = await api.read("status", "status")
            self._buildings = await api.read("buildings", "buildings")
            for raw in self._status:
                normalize_building(raw)
            if not self._status:
                raise DeviceError("No buildings found")
            self._credentials = dict(credentials)
        finally:
            session.detach()

    def _data(self, building_id):
        status = normalize_building(record(self._status, building_id))
        metadata = record(self._buildings, building_id)
        timezone = metadata.get("tz")
        try:
            ZoneInfo(timezone)
        except TypeError, ValueError, ZoneInfoNotFoundError:
            raise DeviceError("Invalid building timezone") from None
        if not status["units"]:
            raise DeviceError("Building has no units")
        return {
            **self._credentials,
            "building_id": building_id,
            "unit_ids": sorted(u["id"] for u in status["units"]),
            "timezone": timezone,
        }

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await self._discover(user_input)
            except AuthError:
                errors["base"] = "invalid_auth"
            except ApiError, KeyError, TypeError:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_building()
        return self.async_show_form(
            step_id="user", data_schema=CREDENTIALS, errors=errors
        )

    async def async_step_building(self, user_input=None):
        errors = {}
        if user_input is not None:
            identity = user_input["building_id"]
            try:
                data = self._data(identity)
            except ApiError:
                errors["base"] = "invalid_device"
            else:
                await self.async_set_unique_id(str(identity))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=record(self._status, identity)["name"], data=data
                )
        choices = {b["id"]: f"{b['name']} ({len(b['units'])})" for b in self._status}
        return self.async_show_form(
            step_id="building",
            data_schema=vol.Schema({vol.Required("building_id"): vol.In(choices)}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await self._discover(user_input)
                data = self._data(entry.data["building_id"])
                # Credential renewal never silently accepts a changed group.
                data["unit_ids"] = entry.data["unit_ids"]
            except AuthError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=data)
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=CREDENTIALS, errors=errors
        )

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors = {}
        try:
            await self._discover(entry.data)
            data = self._data(entry.data["building_id"])
        except ApiError:
            return self.async_abort(reason="cannot_connect")
        units = ", ".join(
            u["name"] for u in record(self._status, entry.data["building_id"])["units"]
        )
        if user_input is not None:
            return self.async_update_reload_and_abort(entry, data_updates=data)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"units": units},
        )
