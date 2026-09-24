"""Structural diagnostics without account, IDs, names or raw telemetry."""


async def async_get_config_entry_diagnostics(hass, entry):
    c = entry.runtime_data
    return {
        "version": 2,
        "last_update_success": c.last_update_success,
        "configured_unit_count": len(c.controller.unit_ids),
        "reported_unit_count": len(c.data["units"]),
        "control_ready": c.controller.ready,
        "profile_count": len(c.profiles),
    }
