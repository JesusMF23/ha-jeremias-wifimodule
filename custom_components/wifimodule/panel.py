"""Authenticated, admin-only panel API. No credentials leave the backend."""

from pathlib import Path

import voluptuous as vol
from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.exceptions import HomeAssistantError

from .api import ApiError
from .const import DOMAIN, VERSION
from .models import integer, revision

OPERATIONS = [
    "list",
    "view",
    "control",
    "activate",
    "edit_day",
    "profile",
    "mode",
    "history",
]


async def dispatch(hass, message):
    entries = hass.data[DOMAIN]["entries"]
    operation = message["operation"]
    if operation == "list":
        return [
            {"entry_id": identity, "name": c.config_entry.title}
            for identity, c in entries.items()
        ]
    identity = message.get("entry_id")
    if identity not in entries:
        raise HomeAssistantError("Integration entry is not loaded")
    coordinator = entries[identity]
    control = coordinator.controller
    data = message.get("data", {})
    if operation == "view":
        await coordinator.async_request_refresh()
        if not coordinator.last_update_success:
            raise HomeAssistantError("Cloud unavailable")
        profiles, modes = await control.profiles(), await control.modes()
        profile = data.get("profile_id", coordinator.data.get("profile_id"))
        week = await control.week(profile) if profile is not None else None
        building_keys = (
            "name",
            "id",
            "profile_id",
            "manual_active",
            "manual_speed",
            "manual_mode",
            "manual_bypass",
            "manual_override_until",
        )
        building = {k: coordinator.data.get(k) for k in building_keys}
        units = [
            {k: u.get(k) for k in ("id", "name", "last_comm", "fw", "values")}
            for u in coordinator.data["units"]
        ]
        return {
            "building": building,
            "units": units,
            "ready": control.ready,
            "profiles": [{k: p.get(k) for k in ("id", "name")} for p in profiles],
            "modes": [
                {
                    k: m.get(k)
                    for k in (
                        "id",
                        "name",
                        "color",
                        "speed",
                        "mode",
                        "bypass",
                        "off",
                        "boost",
                    )
                }
                for m in modes
            ],
            "profile_id": profile,
            "week": week,
            "revision": revision(week) if week is not None else None,
            "timezone": str(control.timezone),
            "duration": control.duration,
        }
    if operation == "history":
        return await control.history(
            data["unit_id"], data.get("start"), data.get("end")
        )
    if operation == "control":
        allowed = {"speed", "bypass", "mode", "duration", "schedule"}
        if set(data) - allowed:
            raise HomeAssistantError("Unknown control fields")
        if "schedule" in data and type(data["schedule"]) is not bool:
            raise HomeAssistantError("Invalid schedule flag")
        return await coordinator.command(control.control, **data)
    if operation == "activate":
        return await coordinator.command(control.activate, integer(data["profile_id"]))
    if operation == "edit_day":
        return await coordinator.command(
            control.edit_day,
            data["profile_id"],
            data["day"],
            data["rows"],
            data["revision"],
        )
    if operation in ("profile", "mode"):
        method = (
            control.mutate_profile if operation == "profile" else control.mutate_mode
        )
        return await coordinator.command(method, data["operation"], data["item"])
    raise HomeAssistantError("Unsupported operation")


@websocket_api.websocket_command(
    {
        vol.Required("type"): "wifimodule/manage",
        vol.Required("operation"): vol.In(OPERATIONS),
        vol.Optional("entry_id"): str,
        vol.Optional("data", default={}): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_manage(hass, connection, msg):
    try:
        result = await dispatch(hass, msg)
    except ApiError, HomeAssistantError, KeyError, TypeError, ValueError:
        connection.send_error(
            msg["id"],
            "operation_failed",
            "Operation not confirmed. Reload and check credentials, device communication and input values.",
        )
    else:
        connection.send_result(msg["id"], result)


async def async_setup_panel(hass):
    if hass.data[DOMAIN].get("panel_registered"):
        return
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                "/wifimodule_static",
                str(Path(__file__).parent / "frontend"),
                cache_headers=False,
            )
        ]
    )
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path="jeremias",
        webcomponent_name="jeremias-panel",
        sidebar_title="Jeremias",
        sidebar_icon="mdi:hvac",
        module_url=f"/wifimodule_static/panel.js?v={VERSION}",
        require_admin=True,
    )
    websocket_api.async_register_command(hass, websocket_manage)
    hass.data[DOMAIN]["panel_registered"] = True
