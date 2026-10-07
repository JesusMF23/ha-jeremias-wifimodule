"""Return timers and independent bypass use real lifecycle state."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from test_automatic import make_auto

from custom_components.wifimodule.automatic import AutomaticControl


async def test_manual_timer_survives_restart_and_returns_to_automatic():
    a, c, _ = make_auto(False)
    end = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
    a.manual_control.record(
        {"manual": True, "mode": "manual", "speed": 0, "switch": "never"},
        0,
        return_to="automatic",
        expires_at=end,
    )
    restored = AutomaticControl(a.hass, c)
    assert restored.snapshot["manual_timer"]["expires_at"] == end
    with patch(
        "custom_components.wifimodule.manual_control.datetime", wraps=datetime
    ) as clock:
        clock.now.return_value = datetime.fromisoformat(end) + timedelta(seconds=1)
        await restored.tick(1)
    assert restored.enabled and not restored.manual_control.active
    c.controller.control.assert_not_awaited()


async def test_timed_schedule_is_not_restored_after_deadline():
    a, c, _ = make_auto(False)
    end = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    a.manual_control.record(
        {"manual": True, "mode": "manual", "speed": 0, "switch": "2026-10-07 12:00"},
        0,
        return_to="schedule",
        expires_at=end,
    )
    restored = AutomaticControl(a.hass, c)
    await restored.tick(5)
    assert restored.mode == "schedule"
    assert not restored.manual_control.active
    c.controller.control.assert_not_awaited()


async def test_bypass_keeps_automatic_and_is_used_for_future_speed_changes():
    a, c, _ = make_auto()
    c.controller.data["units"][0]["values"]["byp"] = 0
    await a.set_bypass(True)
    assert a.enabled and a.snapshot["bypass_requested"] is True
    assert c.controller.control.call_args.kwargs["bypass"] is True
    restored = AutomaticControl(a.hass, c)
    await restored.tick(0)
    await restored.tick(30)
    assert c.controller.control.call_args.kwargs["bypass"] is True


async def test_invalid_bypass_does_not_change_mode():
    a, c, _ = make_auto()
    with pytest.raises(ValueError):
        await a.set_bypass("on")
    assert a.enabled
    c.controller.control.assert_not_awaited()


async def test_failed_bypass_write_is_not_replayed_after_restart():
    from custom_components.wifimodule.api import DeviceError

    a, c, _ = make_auto()
    c.controller.control.side_effect = DeviceError("unknown result")
    with pytest.raises(DeviceError):
        await a.set_bypass(True)
    restored = AutomaticControl(a.hass, c)
    await restored.tick(10)
    assert not restored.enabled and not restored.manual_control.active
    assert c.controller.control.await_count == 1


async def test_selecting_manual_cancels_pending_return():
    a, c, _ = make_auto(False)
    end = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    a.manual_control.record(
        {"manual": True, "mode": "manual", "speed": 0, "switch": "never"},
        0,
        return_to="automatic",
        expires_at=end,
    )
    await a.configure(enabled=False)
    restored = AutomaticControl(a.hass, c)
    assert restored.manual_control.expires_at is None
    assert not restored.enabled


async def test_uncertain_bypass_after_settings_edit_stops_automatic_retries():
    from custom_components.wifimodule.api import DeviceError

    a, c, _ = make_auto()

    async def uncertain(**kwargs):
        await a.configure(settings={"co2_target": 850})
        raise DeviceError("unknown outcome")

    c.controller.control.side_effect = uncertain
    with pytest.raises(DeviceError):
        await a.set_bypass(True)
    assert not a.enabled
    assert AutomaticControl(a.hass, c).status == "command_error"
