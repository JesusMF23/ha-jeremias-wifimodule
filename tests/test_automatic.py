"""Home Assistant automatic-control lifecycle and race regressions."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import State

from custom_components.wifimodule.api import DeviceError
from custom_components.wifimodule.automatic import AutomaticControl
from custom_components.wifimodule.controller import Controller
from custom_components.wifimodule.coordinator import Coordinator


def make_auto(enabled=True):
    state = State(
        "sensor.room", "1500", {"unit_of_measurement": "ppm", "friendly_name": "Room"}
    )
    hass = Mock(data={})
    hass.states.get = lambda entity: state if entity == "sensor.room" else None
    entry = SimpleNamespace(
        options={
            "automatic": {
                "enabled": enabled,
                "sensors": {"co2": ["sensor.room"]},
                "settings": {"filter_rise_seconds": 0, "filter_fall_seconds": 0},
            }
        },
        entry_id="demo",
    )

    def update(e, options):
        e.options = options

    hass.config_entries.async_update_entry = update
    controller = Mock(ready=True, lock=asyncio.Lock())
    controller.data = {
        "manual_active": False,
        "units": [{"values": {"spe": 2, "pwr": 1, "bst": 0, "err": 0}}],
    }
    controller.control = AsyncMock()
    c = Mock(
        controller=controller, config_entry=entry, last_update_success=True, hass=hass
    )
    c.async_request_refresh = AsyncMock()
    auto = AutomaticControl(hass, c)
    return auto, c, state


async def test_manual_mode_never_sends_even_with_high_demand():
    a, c, _ = make_auto(False)
    await a.tick(0)
    await a.tick(1000)
    c.controller.control.assert_not_awaited()
    assert a.status == "manual"


async def test_automatic_fast_rise_uses_existing_controller_with_expiring_lease():
    a, c, _ = make_auto()
    await a.tick(0)
    await a.tick(30)
    assert c.controller.control.await_count == 1
    k = c.controller.control.call_args.kwargs
    assert (k["speed"], k["mode"], k["duration"]) == (7, "manual", 15)
    assert k["_guard"]()
    assert a.status == "awaiting_device"


async def test_manual_invalidates_guard_and_persists_without_command():
    a, c, _ = make_auto()
    await a.tick(0)
    await a.tick(30)
    guard = c.controller.control.call_args.kwargs["_guard"]
    await a.configure(enabled=False)
    assert not guard() and not c.config_entry.options["automatic"]["enabled"]
    count = c.controller.control.await_count
    await a.tick(500)
    assert c.controller.control.await_count == count


async def test_failed_write_disables_without_blind_retry():
    a, c, _ = make_auto()
    c.controller.control.side_effect = DeviceError("write outcome unknown")
    await a.tick(0)
    await a.tick(30)
    await a.tick(500)
    assert c.controller.control.await_count == 1 and not a.enabled
    assert a.status == "command_error"
    restored = AutomaticControl(a.hass, c)
    assert not restored.enabled and restored.status == "command_error"


async def test_waits_for_equipment_freshness_and_acknowledgement():
    a, c, _ = make_auto()
    c.controller.ready = False
    await a.tick(0)
    await a.tick(60)
    assert a.status == "device_unavailable"
    c.controller.control.assert_not_awaited()
    c.controller.ready = True
    await a.tick(70)
    await a.tick(100)
    assert a.status == "awaiting_device"
    await a.tick(281)
    assert not a.enabled and a.status == "device_timeout"


async def test_restarted_automatic_does_not_replay_old_delay():
    a, c, _ = make_auto()
    await a.tick(0)
    b = AutomaticControl(a.hass, c)
    await b.tick(300)
    c.controller.control.assert_not_awaited()
    await b.tick(330)
    c.controller.control.assert_awaited_once()


async def test_sensor_configuration_rejects_wrong_units_and_unknown_entities():
    a, _, _ = make_auto(False)
    with pytest.raises(ValueError):
        await a.configure(sensors={"tvoc": ["sensor.room"]})
    with pytest.raises(ValueError):
        await a.configure(sensors={"co2": ["sensor.missing"]})
    with pytest.raises(ValueError):
        await a.configure(settings={"min_speed": 7, "max_speed": 2})


async def test_controller_checks_guard_after_poll_before_write():
    api = Mock(write=AsyncMock())
    c = Controller(api, 1, [2], "UTC")
    c.data = {
        "manual_active": True,
        "manual_bypass": 0,
        "manual_mode": "manual",
        "units": [{"id": 2, "values": {}}],
    }
    c.heartbeats = {2: SimpleNamespace(fresh=True)}
    c.poll = AsyncMock(return_value=c.data)
    with pytest.raises(DeviceError):
        await c.control(speed=3, mode="manual", duration=15, _guard=lambda: False)
    api.write.assert_not_awaited()


async def test_widget_command_stops_auto_before_existing_manual_command():
    a, c, _ = make_auto()
    c.automatic = a
    await Coordinator.command(c, c.controller.control, speed=2)
    assert not a.enabled
    c.controller.control.assert_awaited_once_with(speed=2)


async def test_reenable_after_manual_starts_new_session():
    a, c, _ = make_auto()
    await a.tick(0)
    await a.tick(30)
    await a.configure(enabled=False)
    await a.configure(enabled=True)
    await a.tick(500)
    assert a.enabled and a.status == "rising"
    await a.tick(530)
    assert c.controller.control.await_count == 2


async def test_healthy_unchanged_speed_renews_lease_but_missing_input_does_not():
    a, c, _ = make_auto()
    await a.tick(0)
    await a.tick(30)
    c.controller.data.update(manual_active=True, manual_mode="manual", manual_speed=7)
    c.controller.data["units"][0]["values"]["spe"] = 7
    await a.tick(40)
    await a.tick(329)
    assert c.controller.control.await_count == 1
    await a.tick(330)
    assert c.controller.control.await_count == 2
    a.hass.states.get = lambda entity: None
    await a.tick(340)
    await a.tick(630)
    assert c.controller.control.await_count == 2 and a.status == "no_data"


async def test_external_cloud_schedule_is_respected():
    a, c, _ = make_auto()
    await a.tick(0)
    await a.tick(30)
    c.controller.data["units"][0]["values"]["spe"] = 7
    await a.tick(160)
    assert not a.enabled and a.status == "external_control"


async def test_no_overlap_and_stop_invalidates_work_waiting_on_io():
    a, c, _ = make_auto()
    entered, release = asyncio.Event(), asyncio.Event()

    async def write(**kwargs):
        entered.set()
        await release.wait()
        if not kwargs["_guard"]():
            raise DeviceError("cancelled")

    c.controller.control.side_effect = write
    await a.tick(0)
    task = asyncio.create_task(a.tick(30))
    await entered.wait()
    await a.tick(40)
    await a.stop()
    release.set()
    await task
    assert c.controller.control.await_count == 1 and a.last_speed is None


async def test_guard_rejects_sensor_loss_during_network_poll():
    a, c, _ = make_auto()
    await a.tick(0)
    await a.tick(30)
    guard = c.controller.control.call_args.kwargs["_guard"]
    a.hass.states.get = lambda entity: None
    assert not guard()


@pytest.mark.parametrize("change", ["sensor_loss", "settings"])
async def test_unknown_write_failure_stops_even_if_context_changes(change):
    a, c, _ = make_auto()

    async def write(**_kwargs):
        if change == "sensor_loss":
            a.hass.states.get = lambda entity: None
        else:
            await a.configure(settings={"co2_target": 850})
        raise DeviceError("Unknown write outcome")

    c.controller.control.side_effect = write
    await a.tick(0)
    await a.tick(30)
    assert not a.enabled and a.status == "command_error"
    assert not c.config_entry.options["automatic"]["enabled"]


async def test_successful_inflight_command_remains_tracked_after_settings_edit():
    a, c, _ = make_auto()

    async def write(**_kwargs):
        await a.configure(settings={"co2_target": 850})

    c.controller.control.side_effect = write
    await a.tick(0)
    await a.tick(30)
    assert a.last_speed == 7 and a.last_sent == 30 and a.awaiting


async def test_long_fall_retains_pending_timer_while_renewing_lease():
    a, c, _ = make_auto()
    await a.configure(settings={"fall_seconds": 3600})
    await a.tick(0)
    await a.tick(30)
    c.controller.data.update(manual_active=True, manual_mode="manual", manual_speed=7)
    c.controller.data["units"][0]["values"]["spe"] = 7
    state = State("sensor.room", "600", {"unit_of_measurement": "ppm"})
    a.hass.states.get = lambda entity: state
    for now in range(40, 3701, 10):
        await a.tick(now)
    speeds = [call.kwargs["speed"] for call in c.controller.control.call_args_list]
    assert speeds.count(7) >= 10 and speeds[-1] == 6
    assert a.enabled


async def test_settings_edit_preserves_minimum_command_interval():
    a, c, _ = make_auto()
    await a.configure(settings={"minimum_interval": 600})
    await a.tick(0)
    await a.tick(30)
    c.controller.data.update(manual_active=True, manual_mode="manual", manual_speed=7)
    c.controller.data["units"][0]["values"]["spe"] = 7
    await a.tick(40)
    await a.configure(settings={"co2_target": 850})
    await a.tick(50)
    await a.tick(330)
    assert c.controller.control.await_count == 1
    await a.tick(630)
    assert c.controller.control.await_count == 2


@pytest.mark.parametrize("fresh_values", [{"spe": 7}, {"bst": 1}, {"err": 2}])
async def test_guard_uses_fresh_physical_state_after_poll(fresh_values):
    a, c, _ = make_auto()
    a.sensors["co2"].append("sensor.missing")
    await a.configure(settings={"max_speed": 5})
    await a.tick(0)
    await a.tick(30)
    guard = c.controller.control.call_args.kwargs["_guard"]
    c.controller.data["units"][0]["values"].update(fresh_values)
    assert not guard()
