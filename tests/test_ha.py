"""Exercise HA entity, config flow and real authorization wrappers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.wifimodule.api import DeviceError
from custom_components.wifimodule.config_flow import WifiModuleConfigFlow
from custom_components.wifimodule.panel import websocket_manage
from custom_components.wifimodule.sensor import Telemetry


def test_sensor_recovers_initial_missing_type_and_rejects_type_change():
    unit = {"id": 2, "values": {}}
    coordinator = Mock(data={"units": [unit]}, controller=Mock(building_id=1))
    sensor = Telemetry(coordinator, unit, "aqs1")
    assert sensor.native_value is None
    unit["values"] = {"aqs1t": 1, "aqs1": 650}
    with patch.object(CoordinatorEntity, "_handle_coordinator_update"):
        sensor._handle_coordinator_update()
    assert sensor.native_value == 650 and sensor.device_class == SensorDeviceClass.CO2
    unit["values"] = {"aqs1t": 2, "aqs1": 450}
    assert sensor.native_value is None


def test_discovery_uses_cloud_timezone_and_building_membership():
    flow = WifiModuleConfigFlow()
    flow._credentials = {"username": "test@example.invalid", "password": "test-only"}
    flow._status = [{"id": 1, "name": "Demo", "units": [{"id": 2, "status": "spe:2"}]}]
    flow._buildings = [{"id": 1, "tz": "Europe/Madrid"}]
    data = flow._data(1)
    assert data["unit_ids"] == [2] and data["timezone"] == "Europe/Madrid"
    flow._buildings[0]["tz"] = "Invalid/Zone"
    with pytest.raises(DeviceError):
        flow._data(1)


def test_real_websocket_wrapper_denies_non_admin_before_dispatch():
    connection = Mock(user=SimpleNamespace(is_admin=False))
    message = {
        "id": 1,
        "type": "wifimodule/manage",
        "operation": "control",
        "data": {"speed": 8},
    }
    with patch(
        "custom_components.wifimodule.panel.dispatch", new_callable=AsyncMock
    ) as dispatch:
        with pytest.raises(Unauthorized):
            websocket_manage(Mock(), connection, message)
    dispatch.assert_not_awaited()


async def test_unload_only_removes_entry_after_platform_success():
    from custom_components.wifimodule import async_unload_entry

    hass = Mock(data={"wifimodule": {"entries": {"demo": "coordinator"}}})
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    entry = SimpleNamespace(entry_id="demo")
    assert not await async_unload_entry(hass, entry)
    assert "demo" in hass.data["wifimodule"]["entries"]
    hass.config_entries.async_unload_platforms.return_value = True
    assert await async_unload_entry(hass, entry)
    assert not hass.data["wifimodule"]["entries"]
