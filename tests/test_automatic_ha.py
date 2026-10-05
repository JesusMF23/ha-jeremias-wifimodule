"""Exercise actual Home Assistant objects, entities and options forms."""

from types import MappingProxyType
from unittest.mock import Mock, patch

from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.wifimodule.automatic import AutomaticControl
from custom_components.wifimodule.controller import Controller
from custom_components.wifimodule.coordinator import Coordinator
from custom_components.wifimodule.number import RegulationNumber
from custom_components.wifimodule.options_flow import WifiModuleOptionsFlow
from custom_components.wifimodule.select import RegulationMode
from custom_components.wifimodule.sensor import RegulationStatus


def setup(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    entry = ConfigEntry(
        domain="wifimodule",
        title="Test",
        version=2,
        minor_version=1,
        data={"building_id": 1, "unit_ids": [2], "timezone": "UTC"},
        options={},
        source="user",
        unique_id="1",
        discovery_keys=MappingProxyType({}),
        subentries_data=[],
    )
    controller = Controller(Mock(), 1, [2], "UTC")
    controller.data = {
        "name": "Test",
        "units": [{"id": 2, "values": {"spe": 2, "pwr": 1, "err": 0, "bst": 0}}],
    }
    c = Coordinator(hass, entry, controller)
    c.async_set_updated_data(controller.data)
    c.automatic = AutomaticControl(hass, c)
    entry.runtime_data = c
    return hass, entry, c


async def test_native_controls_are_available_offline_and_restore_options(tmp_path):
    hass, entry, c = setup(tmp_path)
    a = c.automatic
    hass.states.async_set("sensor.zone", "900", {"unit_of_measurement": "ppm"})
    with patch.object(hass.config_entries, "async_update_entry") as update:
        # Stand-in only for disk writes; real states, entities and form classes below.
        mode = RegulationMode(c)
        number = RegulationNumber(c, "co2_target")
        status = RegulationStatus(c)
        c.last_update_success = False
        assert mode.available and number.available and status.available
        await a.configure(sensors={"co2": ["sensor.zone"]})
        await number.async_set_native_value(850)
        await mode.async_select_option("automatic")
        stored = update.call_args.kwargs["options"]
        assert (
            stored["automatic"]["enabled"]
            and stored["automatic"]["settings"]["co2_target"] == 850
        )
        assert status.native_value == "warming_up"
        assert a.readings()[0].numeric(900) == 900
        await mode.async_select_option("manual")
        assert mode.current_option == "manual"
    await c.async_shutdown()
    await hass.async_stop()


async def test_options_form_contains_actual_entity_selectors_and_all_settings(tmp_path):
    hass, entry, c = setup(tmp_path)
    flow = WifiModuleOptionsFlow()
    flow.hass = hass
    with patch.object(type(flow), "config_entry", property(lambda _self: entry)):
        form = await flow.async_step_init()
    assert form["type"] == "form"
    schema = form["data_schema"]
    keys = {str(k) for k in schema.schema}
    assert {
        "co2_sensors",
        "tvoc_sensors",
        "humidity_sensors",
        "aqi_sensors",
        "min_speed",
        "max_speed",
        "co2_target",
    } <= keys
    await c.async_shutdown()
    await hass.async_stop()


async def test_runtime_timer_unload_and_entity_listener(tmp_path):
    hass, entry, c = setup(tmp_path)
    with patch(
        "custom_components.wifimodule.automatic.async_track_time_interval"
    ) as track:
        cancel = Mock()
        track.return_value = cancel
        c.automatic.start()
        assert track.call_args.args[2].total_seconds() == 10
        await c.automatic.stop()
        cancel.assert_called_once()
    assert c.automatic._closed
    await c.async_shutdown()
    await hass.async_stop()


async def test_options_remain_editable_when_cloud_setup_has_failed(tmp_path):
    hass, entry, c = setup(tmp_path)
    del entry.runtime_data
    hass.states.async_set("sensor.zone", "900", {"unit_of_measurement": "ppm"})
    flow = WifiModuleOptionsFlow()
    flow.hass = hass
    with patch.object(type(flow), "config_entry", property(lambda _self: entry)):
        form = await flow.async_step_init()
        assert form["type"] == "form"
        result = await flow.async_step_init(
            {
                **c.automatic.settings.as_dict(),
                "co2_sensors": ["sensor.zone"],
                "co2_target": 850,
            }
        )
    assert result["type"] == "create_entry"
    assert result["data"]["automatic"]["settings"]["co2_target"] == 850
    assert result["data"]["automatic"]["sensors"]["co2"] == ["sensor.zone"]
    await c.async_shutdown()
    await hass.async_stop()
