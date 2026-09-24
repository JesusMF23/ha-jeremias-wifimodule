from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from custom_components.wifimodule.api import DeviceError
from custom_components.wifimodule.controller import Controller
from custom_components.wifimodule.models import revision


@pytest.fixture
def controller():
    api = AsyncMock()
    data = {
        "id": 1,
        "name": "House",
        "manual_active": True,
        "manual_speed": 2,
        "manual_bypass": 0,
        "manual_mode": "manual",
        "profile_id": 10,
        "units": [
            {
                "id": 2,
                "name": "Unit",
                "last_comm": "2026-01-01 12:00:00",
                "status": "pwr:1,spe:2,bst:0,byp:0,moa:0,fil:100,err:0",
            }
        ],
    }
    week = {f"d{d}": [{"time": 0, "mode_id": 20}] for d in range(7)}

    async def read(endpoint, key):
        if key == "status":
            return [deepcopy(data)]
        if key == "profiles":
            return [{"id": 10, "name": "Main"}, {"id": 11, "name": "Spare"}]
        if key == "modes":
            return [{"id": 20, "name": "Low"}]
        if key == "schedule":
            return deepcopy(week)
        raise AssertionError(endpoint)

    api.read.side_effect = read
    c = Controller(api, 1, [2], "Europe/Madrid")
    return c, api, data, week


async def test_stale_edit_does_not_write(controller):
    c, api, _, week = controller
    with pytest.raises(DeviceError):
        await c.edit_day(10, 1, [{"time": 0, "mode": 20}], "old")
    api.write.assert_not_awaited()


async def test_edit_day_scope_and_payload(controller):
    c, api, _, week = controller
    await c.edit_day(
        10, 1, [{"time": 0, "mode": 20}, {"time": 420, "mode": 20}], revision(week)
    )
    api.write.assert_awaited_once_with(
        "edit-schedule",
        {
            "building": 1,
            "profile": 10,
            "wday": 1,
            "schedule": [{"time": 0, "mode": 20}, {"time": 420, "mode": 20}],
        },
    )


async def test_foreign_profile_never_written(controller):
    c, api, _, week = controller
    with pytest.raises(DeviceError):
        await c.edit_day(999, 1, [{"time": 0, "mode": 20}], revision(week))
    api.write.assert_not_awaited()


async def test_membership_change_prevents_control(controller):
    c, api, data, _ = controller
    await c.poll()
    data["units"].append({**data["units"][0], "id": 3})
    with pytest.raises(DeviceError):
        await c.control(speed=2)
    api.write.assert_not_awaited()


async def test_boost_is_bounded_and_timed(controller):
    c, api, data, _ = controller
    await c.poll()
    data["units"][0]["last_comm"] = "2026-01-01 12:01:00"
    await c.control(speed=8, duration=5)
    body = api.write.call_args.args[1]
    assert body["speed"] == 8 and body["switch"] != "never" and body["bypass"] is False
    with pytest.raises(DeviceError):
        await c.control(speed=8, duration=0)


async def test_used_mode_cannot_be_deleted(controller):
    c, api, _, _ = controller
    with pytest.raises(DeviceError):
        await c.mutate_mode("delete", {"id": 20})
    api.write.assert_not_awaited()


async def test_profile_activation_checks_current_membership(controller):
    c, api, data, _ = controller
    data["units"].append({**data["units"][0], "id": 3})
    with pytest.raises(DeviceError):
        await c.activate(11)
    api.write.assert_not_awaited()


async def test_programming_rejects_changed_membership(controller):
    c, api, data, week = controller
    data["units"].append({**data["units"][0], "id": 3})
    with pytest.raises(DeviceError):
        await c.edit_day(10, 1, [{"time": 0, "mode": 20}], revision(week))
    api.write.assert_not_awaited()


async def test_manual_payload_and_activation_after_fresh_communication(controller):
    c, api, data, _ = controller
    await c.poll()
    data["units"][0]["last_comm"] = "2026-01-01 12:01:00"
    await c.control(speed=3, bypass=True, mode="manual", duration=0)
    api.write.assert_awaited_with(
        "unit-config",
        {
            "building": 1,
            "manual": True,
            "speed": 3,
            "bypass": True,
            "mode": "manual",
            "switch": "never",
        },
    )
    await c.activate(11)
    api.write.assert_awaited_with(
        "profiles", {"op": "activate", "data": {"profile": 11, "building": 1}}
    )


async def test_cannot_delete_active_profile(controller):
    c, api, _, _ = controller
    with pytest.raises(DeviceError):
        await c.mutate_profile("delete", {"id": 10})
    api.write.assert_not_awaited()


async def test_profile_creation_and_mode_encoding(controller):
    c, api, _, _ = controller
    await c.mutate_profile("add", {"name": "Holiday"})
    api.write.assert_awaited_with(
        "profiles", {"op": "add", "data": {"name": "Holiday", "building_id": 1}}
    )
    await c.mutate_mode(
        "add",
        {
            "name": "Off",
            "speed": 0,
            "mode": "manual",
            "bypass": False,
            "color": "#112233",
        },
    )
    body = api.write.call_args.args[1]["data"]
    assert body == {
        "name": "Off",
        "building_id": 1,
        "speed": 1,
        "off": True,
        "boost": False,
        "mode": "manual",
        "bypass": 0,
        "color": "#112233",
    }


async def test_weekly_limit_rejects_before_write(controller):
    c, api, _, week = controller
    for day in range(7):
        week[f"d{day}"] = [{"time": i * 60, "mode_id": 20} for i in range(22)]
    with pytest.raises(DeviceError):
        await c.edit_day(
            10, 1, [{"time": i * 60, "mode": 20} for i in range(22)], revision(week)
        )
    api.write.assert_not_awaited()


async def test_history_scope_and_encoded_date_range(controller):
    from urllib.parse import parse_qs, urlsplit

    c, api, data, _ = controller
    original = api.read.side_effect

    async def read(endpoint, key):
        if key == "chart":
            assert parse_qs(urlsplit(endpoint).query) == {
                "unit": ["2"],
                "from": ["2026-01-01 00:00:00"],
                "to": ["2026-01-02 00:00:00"],
            }
            return {"labels": [], "datasets": []}
        return await original(endpoint, key)

    api.read.side_effect = read
    assert await c.history(2, "2026-01-01 00:00:00", "2026-01-02 00:00:00") == {
        "labels": [],
        "datasets": [],
    }
    with pytest.raises(DeviceError):
        await c.history(3)
    with pytest.raises(DeviceError):
        await c.history(2, "2026-01-02 00:00:00", "2026-01-01 00:00:00")
