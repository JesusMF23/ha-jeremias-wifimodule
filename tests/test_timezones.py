"""Timezone resolution stays async while persisted entries keep their names."""

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
                            "status": "pwr:0,spe:4,byp:0,moa:0",
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
        patch("custom_components.wifimodule.async_acquire_bridge", return_value=None),
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
