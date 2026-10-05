"""Configure demand sensors and numeric thresholds using native HA selectors."""

import voluptuous as vol
from homeassistant.config_entries import OptionsFlow
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .automatic import validate_sensors
from .demand import KINDS, PARAMETERS, Settings


class WifiModuleOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None):
        entry = self.config_entry
        automatic = getattr(getattr(entry, "runtime_data", None), "automatic", None)
        stored = entry.options.get("automatic", {})
        sensors = (
            automatic.sensors
            if automatic
            else {k: stored.get("sensors", {}).get(k, []) for k in KINDS}
        )
        settings = (
            automatic.settings
            if automatic
            else Settings.from_dict(stored.get("settings", {}))
        )
        errors = {}
        if user_input is not None:
            try:
                sensors = validate_sensors(
                    self.hass, {k: user_input.get(k + "_sensors", []) for k in KINDS}
                )
                settings = Settings.from_dict({k: user_input[k] for k in PARAMETERS})
                if stored.get("enabled") and not any(sensors.values()):
                    raise ValueError("Select at least one sensor")
                if automatic:
                    await automatic.configure(
                        sensors=sensors, settings=settings.as_dict()
                    )
            except ValueError, KeyError, TypeError:
                errors["base"] = "invalid_automatic_config"
            else:
                return self.async_create_entry(
                    title="",
                    data=dict(entry.options)
                    if automatic
                    else {
                        **entry.options,
                        "automatic": {
                            **stored,
                            "sensors": sensors,
                            "settings": settings.as_dict(),
                        },
                    },
                )
        schema = {
            vol.Optional(k + "_sensors", default=sensors[k]): EntitySelector(
                EntitySelectorConfig(domain="sensor", multiple=True)
            )
            for k in KINDS
        }
        schema.update(
            {
                vol.Required(k, default=getattr(settings, k)): NumberSelector(
                    NumberSelectorConfig(
                        min=low, max=high, step=step, mode=NumberSelectorMode.BOX
                    )
                )
                for k, (_, low, high, step) in PARAMETERS.items()
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema), errors=errors
        )
