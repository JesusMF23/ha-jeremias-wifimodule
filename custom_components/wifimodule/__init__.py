"""Jeremias / WifiModule integration lifecycle."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiohttp import CookieJar
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import ApiError, AuthError, WifiModuleApi
from .const import DOMAIN, PLATFORMS
from .controller import Controller
from .coordinator import Coordinator
from .models import record
from .panel import async_setup_panel


async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {"entries": {}})
    await async_setup_panel(hass)
    return True


async def async_setup_entry(hass, entry):
    session = async_create_clientsession(hass, cookie_jar=CookieJar())
    api = WifiModuleApi(session, entry.data["username"], entry.data["password"])
    timezone = entry.data.get("timezone")
    if timezone is None:
        try:
            timezone = record(
                await api.read("buildings", "buildings"), entry.data["building_id"]
            ).get("tz")
            ZoneInfo(timezone)
        except AuthError:
            raise ConfigEntryAuthFailed("WifiModule authentication required") from None
        except ApiError, TypeError, ValueError, ZoneInfoNotFoundError:
            raise ConfigEntryNotReady("Building timezone unavailable") from None
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "timezone": timezone}
        )
    controller = Controller(
        api, entry.data["building_id"], entry.data["unit_ids"], timezone
    )
    controller.duration = entry.options.get("duration", 30)
    coordinator = Coordinator(hass, entry, controller)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    hass.data[DOMAIN]["entries"][entry.entry_id] = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        hass.data[DOMAIN]["entries"].pop(entry.entry_id, None)
        raise
    return True


async def async_unload_entry(hass, entry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN]["entries"].pop(entry.entry_id, None)
    return unloaded


async def async_migrate_entry(hass, entry):
    if entry.version > 2:
        return False
    if entry.version == 1:
        data = dict(entry.data)
        unit = data.pop("unit_id")
        data.update(unit_ids=[unit], timezone=None)
        registry = er.async_get(hass)
        old = f"{data['building_id']}_{unit}_ventilation"
        entity = registry.async_get_entity_id("fan", DOMAIN, old)
        if entity:
            registry.async_update_entity(
                entity, new_unique_id=f"{data['building_id']}_ventilation"
            )
        hass.config_entries.async_update_entry(
            entry, data=data, version=2, unique_id=str(data["building_id"])
        )
    return True
