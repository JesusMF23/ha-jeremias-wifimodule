"""Setup keeps timezone I/O async, integrations isolated and sensor options intact."""

from types import MappingProxyType
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import dt as dt_util

from custom_components.wifimodule import async_setup_entry
from custom_components.wifimodule.config_flow import WifiModuleConfigFlow


@pytest.fixture
async def setup_entry(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    hass.data["wifimodule"] = {"entries": {}}
    entry = ConfigEntry(
        domain="wifimodule",
        title="Test",
        version=2,
        minor_version=1,
        data={
            "username": "test@example.invalid",
            "password": "test-only",
            "building_id": 1,
            "unit_ids": [2],
        },
        options={},
        source="user",
        unique_id="1",
        discovery_keys=MappingProxyType({}),
        subentries_data=[],
    )
    with patch.object(hass.config_entries, "async_setup", return_value=True):
        await hass.config_entries.async_add(entry)
    entry._async_set_state(hass, ConfigEntryState.SETUP_IN_PROGRESS, None)
    api = AsyncMock()
    status_reads = 0

    async def read(endpoint, key):
        nonlocal status_reads
        if key == "status":
            status_reads += 1
        return {
            "buildings": [{"id": 1, "tz": "Europe/Madrid"}],
            "status": [
                {
                    "id": 1,
                    "name": "Test",
                    "units": [
                        {
                            "id": 2,
                            "status": "pwr:0,spe:4,byp:0,moa:0,bst:0,err:0",
                            "last_comm": f"2026-03-29 03:00:{status_reads:02d}",
                        }
                    ],
                }
            ],
            "profiles": [{"id": 10, "name": "Test"}],
        }[key]

    api.read.side_effect = read
    with (
        patch("custom_components.wifimodule.async_create_clientsession"),
        patch("custom_components.wifimodule.WifiModuleApi", return_value=api),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
    ):
        try:
            yield hass, entry, api
        finally:
            if coordinator := hass.data["wifimodule"]["entries"].get(entry.entry_id):
                await coordinator.automatic.stop()
                await coordinator.async_shutdown()
            await hass.async_stop()


@pytest.mark.parametrize("stored", [None, "Europe/Madrid"])
async def test_setup_resolves_saved_and_discovered_timezone_asynchronously(
    setup_entry, stored
):
    hass, entry, _ = setup_entry
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "timezone": stored}
    )
    with patch.object(
        dt_util, "async_get_time_zone", wraps=dt_util.async_get_time_zone
    ) as resolve:
        assert await async_setup_entry(hass, entry)
    resolve.assert_awaited_once_with("Europe/Madrid")
    assert entry.data["timezone"] == "Europe/Madrid"
    controller = entry.runtime_data.controller
    # A timed return uses the resolved zone, including the spring DST jump.
    await controller.control(
        speed=0,
        bypass=False,
        mode="manual",
        _expires_at="2026-03-29T01:30:00+00:00",
    )
    assert controller.last_control["switch"] == "2026-03-29 03:30"


@pytest.mark.parametrize("stored", [None, "Unknown/Timezone", "", 42])
async def test_unknown_timezone_retries_setup_without_registering_controller(
    setup_entry, stored
):
    hass, entry, api = setup_entry
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "timezone": stored}
    )
    api.read.side_effect = None
    api.read.return_value = [{"id": 1, "tz": "Unknown/Timezone"}]
    with pytest.raises(ConfigEntryNotReady, match="Building timezone unavailable"):
        await async_setup_entry(hass, entry)
    assert entry.entry_id not in hass.data["wifimodule"]["entries"]
    assert entry.data["timezone"] == stored
    api.write.assert_not_awaited()


async def test_discovery_resolves_timezone_asynchronously_and_keeps_name():
    flow = WifiModuleConfigFlow()
    flow._credentials = {"username": "test@example.invalid", "password": "test-only"}
    flow._status = [{"id": 1, "name": "Test", "units": [{"id": 2, "status": "spe:2"}]}]
    flow._buildings = [{"id": 1, "tz": "Europe/Madrid"}]
    with patch.object(
        dt_util, "async_get_time_zone", wraps=dt_util.async_get_time_zone
    ) as resolve:
        data = await flow._async_data(1)
    resolve.assert_awaited_once_with("Europe/Madrid")
    assert data["timezone"] == "Europe/Madrid"
    assert data["unit_ids"] == [2]


async def test_entry_and_sensor_setup_do_not_inspect_foreign_integrations(setup_entry):
    from custom_components.wifimodule.sensor import (
        RegulationStatus,
        Telemetry,
    )
    from custom_components.wifimodule.sensor import (
        async_setup_entry as setup_sensors,
    )

    hass, entry, _ = setup_entry
    entities = []
    with patch.object(
        hass.config_entries, "async_entries", wraps=hass.config_entries.async_entries
    ) as entries:
        assert await async_setup_entry(hass, entry)
        await setup_sensors(hass, entry, entities.extend)
        await entry.runtime_data.automatic.tick(0)
    entries.assert_not_called()
    assert any(isinstance(entity, RegulationStatus) for entity in entities)
    assert {entity.key for entity in entities if isinstance(entity, Telemetry)} == {
        "speed_level",
        "error_code",
        "filter_hours",
        "filter_days_remaining",
        "last_communication",
        "aqs1",
        "aqs2",
    }


async def test_standard_sensor_states_drive_worst_zone_and_restore_saved_settings(
    setup_entry,
):
    from custom_components.wifimodule.automatic import AutomaticControl

    hass, entry, api = setup_entry
    assert await async_setup_entry(hass, entry)
    for entity_id, value, unit, device_class in (
        ("sensor.provider_a_co2", "650", "ppm", "carbon_dioxide"),
        ("sensor.provider_b_co2", "1100", "ppm", "carbon_dioxide"),
        ("sensor.provider_c_voc", "1.5", "ppm", "volatile_organic_compounds_parts"),
    ):
        hass.states.async_set(
            entity_id,
            value,
            {"unit_of_measurement": unit, "device_class": device_class},
        )
    coordinator = entry.runtime_data
    auto = coordinator.automatic
    await auto.configure(
        enabled=True,
        sensors={
            "co2": ["sensor.provider_a_co2", "sensor.provider_b_co2"],
            "tvoc": ["sensor.provider_c_voc"],
        },
        settings={"max_speed": 6, "co2_target": 850, "filter_rise_seconds": 0},
    )
    await coordinator.controller.poll()
    await auto.tick(0)
    await auto.tick(30)
    assert auto.decision.source.entity_id == "sensor.provider_c_voc"
    assert auto.decision.source.numeric(900) == 1500
    assert coordinator.controller.last_control["speed"] == 6
    api.write.assert_awaited_once()
    restored = AutomaticControl(hass, coordinator)
    assert restored.enabled
    assert restored.sensors == auto.sensors
    assert restored.settings.co2_target == 850
    assert restored.settings.max_speed == 6


@pytest.mark.parametrize("state", [None, "unavailable", "restored"])
async def test_removed_bridge_readings_remain_selected_but_never_send_commands(
    setup_entry, state
):
    hass, entry, api = setup_entry
    options = {
        "duration": 45,
        "automatic": {
            "enabled": True,
            "sensors": {"co2": ["sensor.former_bridge_co2"]},
            "settings": {"co2_target": 850, "min_speed": 0, "max_speed": 6},
        },
    }
    hass.config_entries.async_update_entry(entry, options=options)
    if state is not None:
        hass.states.async_set(
            "sensor.former_bridge_co2",
            "1600" if state == "restored" else state,
            {"unit_of_measurement": "ppm", "restored": state == "restored"},
        )
    assert await async_setup_entry(hass, entry)
    coordinator = entry.runtime_data
    await coordinator.controller.poll()
    await coordinator.automatic.tick(0)
    await coordinator.automatic.tick(1000)
    assert coordinator.automatic.status == "no_data"
    assert coordinator.automatic.snapshot["invalid_sensors"] == [
        "sensor.former_bridge_co2"
    ]
    assert entry.options == options
    api.write.assert_not_awaited()
