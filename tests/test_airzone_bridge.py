"""Read-only AirQ adapter: fictional fixtures matching observed field names."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.config_entries import ConfigEntryState

from custom_components.wifimodule.airzone_bridge import AirQBridge, extract_values
from custom_components.wifimodule.airzone_sensor import AirQSensor
from tests.test_automatic_ha import setup

STATUS = {
    "aq_co2": 650,
    "aq_tvoc": 150,
    "humidity": 48,
    "isConnected": True,
    "ws_connected": True,
    "aq_measuring": True,
}


def source(hass):
    device = SimpleNamespace(
        get_id=lambda: "airq-demo", data=lambda: {"available": True}
    )
    client = SimpleNamespace(
        air_quality={"airq-demo": device},
        api_get_device_status=AsyncMock(return_value=deepcopy(STATUS)),
        raw_data=Mock(side_effect=AssertionError("Never replay cached diagnostics")),
    )
    coordinator = SimpleNamespace(
        airzone=client,
        last_update_success=True,
        data={
            "zones": {"zone-demo": {"air-quality-id": "airq-demo", "name": "Bedroom"}}
        },
    )
    entry = SimpleNamespace(
        entry_id="airzone-demo", state=ConfigEntryState.LOADED, runtime_data=coordinator
    )
    return entry, coordinator, client


def test_extract_measurements_without_converting_cai_or_scores():
    assert extract_values(STATUS) == {"co2": 650, "tvoc": 150, "humidity": 48}
    assert extract_values({**STATUS, "aq_co2": None, "aq_co2_score": 90})["co2"] is None
    assert extract_values({**STATUS, "aq_tvoc": float("nan")})["tvoc"] is None
    assert extract_values({**STATUS, "humidity": 110})["humidity"] is None
    assert extract_values({**STATUS, "aq_co2": True})["co2"] is None


def test_inactive_disconnected_or_missing_flags_never_produce_valid_values():
    for flag in ("isConnected", "ws_connected", "aq_measuring"):
        assert not extract_values({**STATUS, flag: False})
        missing = {k: v for k, v in STATUS.items() if k != flag}
        assert not extract_values(missing)
    assert not extract_values({"aq_score": 85, "aq_quality": "good"})


async def test_bridge_reads_existing_client_and_tracks_actual_zone_name(tmp_path):
    hass, entry, wifi = setup(tmp_path)
    src, _coord, client = source(hass)
    bridge = AirQBridge(hass)
    with patch.object(hass.config_entries, "async_entries", return_value=[src]):
        await bridge.async_refresh()
    assert bridge.last_update_success
    key = (src.entry_id, "airq-demo")
    assert bridge.data[key]["name"] == "AirQ Bedroom"
    client.api_get_device_status.assert_awaited_once()
    client.raw_data.assert_not_called()
    sensor = AirQSensor(bridge, key, "co2")
    assert sensor.available and sensor.native_value == 650
    assert sensor.native_unit_of_measurement == "ppm"
    assert sensor.device_class == "carbon_dioxide"
    await bridge.async_shutdown()
    await wifi.async_shutdown()
    await hass.async_stop()


async def test_each_poll_reads_again_and_failure_drops_previous_value(tmp_path):
    hass, entry, wifi = setup(tmp_path)
    src, _coord, client = source(hass)
    bridge = AirQBridge(hass)
    with patch.object(hass.config_entries, "async_entries", return_value=[src]):
        await bridge.async_refresh()
        sensor = AirQSensor(bridge, (src.entry_id, "airq-demo"), "co2")
        client.api_get_device_status.return_value = {**STATUS, "aq_co2": 900}
        await bridge.async_refresh()
        assert sensor.native_value == 900
        client.api_get_device_status.side_effect = TimeoutError
        await bridge.async_refresh()
        assert not sensor.available and sensor.native_value is None
        assert client.api_get_device_status.await_count == 3
    await bridge.async_shutdown()
    await wifi.async_shutdown()
    await hass.async_stop()


async def test_unloaded_or_failed_airzone_source_never_read(tmp_path):
    hass, entry, wifi = setup(tmp_path)
    src, coord, client = source(hass)
    bridge = AirQBridge(hass)
    with patch.object(hass.config_entries, "async_entries", return_value=[src]):
        src.state = ConfigEntryState.NOT_LOADED
        await bridge.async_refresh()
        assert not bridge.data
        src.state = ConfigEntryState.LOADED
        coord.last_update_success = False
        await bridge.async_refresh()
        assert not bridge.data
        client.api_get_device_status.assert_not_awaited()
    await bridge.async_shutdown()
    await wifi.async_shutdown()
    await hass.async_stop()


async def test_source_reloaded_during_request_discards_returned_measurement(tmp_path):
    hass, entry, wifi = setup(tmp_path)
    src, _coord, client = source(hass)
    bridge = AirQBridge(hass)

    async def replaced(_device):
        src.runtime_data = object()
        return STATUS

    client.api_get_device_status.side_effect = replaced
    with patch.object(hass.config_entries, "async_entries", return_value=[src]):
        await bridge.async_refresh()
    assert not bridge.data[(src.entry_id, "airq-demo")]["values"]
    await bridge.async_shutdown()
    await wifi.async_shutdown()
    await hass.async_stop()


async def test_bridge_is_shared_and_only_final_unload_cancels_request(tmp_path):
    import asyncio

    from custom_components.wifimodule.airzone_bridge import (
        async_acquire_bridge,
        async_release_bridge,
    )
    from custom_components.wifimodule.const import DOMAIN

    hass, entry, wifi = setup(tmp_path)
    hass.data[DOMAIN] = {}
    second = SimpleNamespace(entry_id="second-wifi")
    bridge = await async_acquire_bridge(hass, entry)
    assert await async_acquire_bridge(hass, second) is bridge
    src, _coord, client = source(hass)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def pending(_device):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    client.api_get_device_status.side_effect = pending
    with patch.object(hass.config_entries, "async_entries", return_value=[src]):
        task = asyncio.create_task(bridge.async_refresh())
        await started.wait()
        await async_release_bridge(hass, entry)
        assert not cancelled.is_set()
        await async_release_bridge(hass, second)
        await asyncio.gather(task, return_exceptions=True)
    assert cancelled.is_set() and not bridge._pending
    assert "airq_bridge" not in hass.data[DOMAIN]
    await wifi.async_shutdown()
    await hass.async_stop()


async def test_late_discovery_and_one_failed_airq_preserves_other_readings(tmp_path):
    from custom_components.wifimodule.airzone_sensor import async_setup_airq

    hass, entry, wifi = setup(tmp_path)
    bridge = wifi.airq = AirQBridge(hass)
    added = Mock()
    src, _coord, client = source(hass)
    other = SimpleNamespace(
        get_id=lambda: "airq-second", data=lambda: {"available": True}
    )
    client.air_quality["airq-second"] = other

    async def status(device):
        if device is other:
            raise TimeoutError
        return STATUS

    client.api_get_device_status.side_effect = status
    with patch.object(hass.config_entries, "async_entries", return_value=[]):
        await async_setup_airq(entry, added)
        added.assert_not_called()
    with patch.object(hass.config_entries, "async_entries", return_value=[src]):
        await bridge.async_refresh()
        assert len(added.call_args.args[0]) == 6
        entities = added.call_args.args[0]
        assert sum(entity.available for entity in entities) == 3
        await bridge.async_refresh()
        assert added.call_count == 1
    with patch.object(hass.config_entries, "async_entries", return_value=[]):
        await bridge.async_refresh()
        assert not any(entity.available for entity in entities)
    await bridge.async_shutdown()
    await wifi.async_shutdown()
    await hass.async_stop()


async def test_reload_during_second_device_discards_entire_batch_and_skips_later_get(
    tmp_path,
):
    hass, entry, wifi = setup(tmp_path)
    src, _coord, client = source(hass)
    bridge = AirQBridge(hass)
    for device_id in ("second", "third"):
        client.air_quality[device_id] = SimpleNamespace(
            get_id=lambda value=device_id: value, data=lambda: {"available": True}
        )

    async def replaced(device):
        if device.get_id() == "second":
            src.runtime_data = object()
        return STATUS

    client.api_get_device_status.side_effect = replaced
    with patch.object(hass.config_entries, "async_entries", return_value=[src]):
        await bridge.async_refresh()
    assert len(bridge.data) == 3
    assert not any(row["values"] for row in bridge.data.values())
    assert client.api_get_device_status.await_count == 2
    await bridge.async_shutdown()
    await wifi.async_shutdown()
    await hass.async_stop()
