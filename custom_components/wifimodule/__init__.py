"""Jeremias / WifiModule integration lifecycle."""

from aiohttp import CookieJar
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.util import dt as dt_util

from .airzone_bridge import async_acquire_bridge, async_release_bridge
from .api import ApiError, AuthError, WifiModuleApi
from .automatic import AutomaticControl
from .const import DOMAIN, PLATFORMS
from .controller import Controller
from .coordinator import Coordinator
from .models import record
from .panel import async_setup_panel

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {"entries": {}})
    await async_setup_panel(hass)
    return True


async def async_setup_entry(hass, entry):
    session = async_create_clientsession(hass, cookie_jar=CookieJar())
    api = WifiModuleApi(session, entry.data["username"], entry.data["password"])
    timezone_name = entry.data.get("timezone")
    try:
        if timezone_name is None:
            timezone_name = record(
                await api.read("buildings", "buildings"), entry.data["building_id"]
            ).get("tz")
        timezone = (
            await dt_util.async_get_time_zone(timezone_name)
            if isinstance(timezone_name, str) and timezone_name
            else None
        )
    except AuthError:
        raise ConfigEntryAuthFailed("WifiModule authentication required") from None
    except ApiError, TypeError, ValueError:
        raise ConfigEntryNotReady("Building timezone unavailable") from None
    if timezone is None:
        raise ConfigEntryNotReady("Building timezone unavailable")
    if entry.data.get("timezone") is None:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "timezone": timezone_name}
        )
    controller = Controller(
        api, entry.data["building_id"], entry.data["unit_ids"], timezone
    )
    controller.duration = entry.options.get("duration", 30)
    coordinator = Coordinator(hass, entry, controller)
    await coordinator.async_config_entry_first_refresh()
    coordinator.automatic = AutomaticControl(hass, coordinator)
    coordinator.airq = await async_acquire_bridge(hass, entry)

    async def release_airq():
        await async_release_bridge(hass, entry)

    entry.async_on_unload(release_airq)
    entry.runtime_data = coordinator
    hass.data[DOMAIN]["entries"][entry.entry_id] = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        hass.data[DOMAIN]["entries"].pop(entry.entry_id, None)
        raise
    coordinator.automatic.start()
    entry.async_on_unload(coordinator.automatic._cancel)
    return True


async def async_unload_entry(hass, entry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = hass.data[DOMAIN]["entries"].get(entry.entry_id)
        if getattr(coordinator, "automatic", None) is not None:
            await coordinator.automatic.stop()
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
