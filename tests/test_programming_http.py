"""Programming round trips through the real API client and a disposable vendor.

This deliberately does not use a household cloud account: every mutation and
cleanup belongs to this localhost fixture. It is protocol acceptance, not vendor
or equipment certification.
"""

from copy import deepcopy
from datetime import UTC

import pytest
from aiohttp import ClientSession, CookieJar, web

from custom_components.wifimodule import api as api_module
from custom_components.wifimodule.api import (
    ApiError,
    DeviceError,
    ScheduleError,
    WifiModuleApi,
)
from custom_components.wifimodule.controller import Controller
from custom_components.wifimodule.models import revision


@pytest.fixture
async def cloud(monkeypatch, request):
    readback = getattr(request, "param", None)
    modes = [{"id": 20, "name": "Low"}]
    profiles = [{"id": 10, "name": "Main"}]
    base = {f"d{i}": [{"time": 0, "mode_id": 20}] for i in range(7)}
    if readback == "saved_off_mode":
        modes.extend(
            {
                "id": identity,
                "name": f"HA Schedule {speed}-0{suffix}",
                "speed": speed,
                "bypass": 0,
                "boost": 0,
                "mode": "manual",
            }
            for identity, speed, suffix in [
                (21, 2, ""),
                (22, 3, ""),
                (23, 0, ""),
                (24, 0, " (2)"),
            ]
        )
        base["d1"] = [
            {"time": 0, "mode_id": 22},
            {"time": 480, "mode_id": 21},
            {"time": 1260, "mode_id": 22},
        ]
    weeks = {10: deepcopy(base)}
    building = {
        "id": 1,
        "name": "Test",
        "profile_id": 10,
        "manual_active": False,
        "units": [{"id": 2, "name": "Test", "status": "pwr:0,spe:4,byp:0,bst:0,err:0"}],
    }
    writes = []
    heartbeat = 0

    async def handle(request):
        nonlocal heartbeat
        endpoint = request.match_info["endpoint"]
        if endpoint == "login":
            response = web.json_response({"msg": "success"})
            response.set_cookie("test", "session", httponly=True)
            return response
        assert request.cookies.get("test") == "session"
        if request.method == "GET":
            if endpoint == "status":
                heartbeat += 1
                building["units"][0]["last_comm"] = (
                    f"2026-10-20 12:{heartbeat // 60:02}:{heartbeat % 60:02}"
                )
                return web.json_response({"msg": "status", "status": [building]})
            if endpoint == "schedule":
                return web.json_response(
                    {
                        "msg": "schedule",
                        "schedule": weeks[int(request.query["profile"])],
                    }
                )
            return web.json_response(
                {
                    "msg": endpoint,
                    endpoint: profiles if endpoint == "profiles" else modes,
                }
            )
        body = await request.json()
        writes.append((endpoint, body))
        if endpoint == "edit-schedule":
            weeks[body["profile"]][f"d{body['wday']}"] = [
                {"time": row["time"], "mode_id": row["mode"]}
                for row in body["schedule"]
            ]
            if readback == "legacy_mode":
                return web.json_response({"msg": "schedule"})
        else:
            operation, data = body["op"], body["data"]
            collection = profiles if endpoint == "profiles" else modes
            if operation == "add":
                identity = max(item["id"] for item in collection) + 1
                collection.append({**data, "id": identity})
                if endpoint == "profiles":
                    weeks[identity] = deepcopy(base)
                elif readback == "legacy_mode":
                    collection[-1].update(
                        speed=str(data["speed"]),
                        bypass=str(data["bypass"]),
                        boost=None,
                    )
                    return web.json_response({"msg": "modes", "modes": collection})
                elif data["off"] and readback in ("zero_off_speed", "null_off_speed"):
                    collection[-1]["speed"] = (
                        0 if readback == "zero_off_speed" else None
                    )
                elif data["off"] and readback in ("off_flag_omitted", "saved_off_mode"):
                    collection[-1]["speed"] = 0
                    collection[-1].pop("off")
            elif operation == "edit":
                item = next(item for item in collection if item["id"] == data["id"])
                item.update(data)
            elif operation == "activate":
                building["profile_id"] = data["profile"]
            elif operation == "delete":
                collection[:] = [
                    item for item in collection if item["id"] != data["id"]
                ]
        return web.json_response({"msg": "success"})

    app = web.Application()
    app.router.add_route("*", "/api/{endpoint}", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    monkeypatch.setattr(api_module, "BASE_URL", f"http://127.0.0.1:{port}/api/")
    try:
        async with ClientSession(cookie_jar=CookieJar(unsafe=True)) as session:
            client = WifiModuleApi(session, "test@example.invalid", "test-only")
            yield Controller(client, 1, [2], UTC), writes
    finally:
        await runner.cleanup()


async def test_profile_mode_and_weekly_schedule_round_trip(cloud):
    c, writes = cloud
    await c.poll()
    await c.mutate_profile("add", {"name": "Disposable"})
    profile = (await c.profiles())[-1]["id"]
    await c.mutate_profile("edit", {"id": profile, "name": "Renamed"})
    assert (await c.profiles())[-1]["name"] == "Renamed"
    mode = {
        "name": "Test off",
        "speed": 0,
        "mode": "manual",
        "bypass": False,
        "color": "#112233",
    }
    await c.mutate_mode("add", mode)
    identity = (await c.modes())[-1]["id"]
    await c.mutate_mode("edit", {**mode, "id": identity, "speed": 3, "bypass": True})
    actual = (await c.modes())[-1]
    assert actual["speed"] == 3 and actual["bypass"] == 1 and not actual["off"]
    original = await c.week(profile)
    rows = [{"time": 0, "mode": 20}, {"time": 420, "mode": identity}]
    await c.edit_day(profile, 1, rows, revision(original))
    changed = await c.week(profile)
    assert changed["d1"][1] == {"time": 420, "mode_id": identity}
    count = len(writes)
    with pytest.raises(DeviceError, match="Schedule changed"):
        await c.edit_day(profile, 1, rows, revision(original))
    with pytest.raises(DeviceError, match="used by a schedule"):
        await c.mutate_mode("delete", {"id": identity})
    assert len(writes) == count
    await c.edit_day(profile, 2, rows, revision(changed))
    assert (await c.week(profile))["d2"] == changed["d1"]
    await c.activate(profile)
    assert (await c.poll())["profile_id"] == profile
    with pytest.raises(DeviceError, match="another profile"):
        await c.mutate_profile("delete", {"id": profile})
    await c.activate(10)
    await c.mutate_profile("delete", {"id": profile})
    await c.mutate_mode("delete", {"id": identity})
    assert [item["id"] for item in await c.profiles()] == [10]
    assert [item["id"] for item in await c.modes()] == [20]


async def test_direct_speeds_round_trip_and_reuse_modes_on_copy(cloud):
    c, writes = cloud
    rows = [
        {"time": 0, "mode": 20},
        {"time": 420, "speed": 3, "bypass": True},
        {"time": 720, "speed": 3, "bypass": False},
        {"time": 1080, "speed": 3, "bypass": True},
        {"time": 1320, "speed": 0, "bypass": False},
    ]
    original = await c.week(10)
    await c.edit_day(10, 1, rows, revision(original))
    changed = await c.week(10)
    saved = changed["d1"]
    assert saved[0] == original["d1"][0]
    assert saved[1]["mode_id"] == saved[3]["mode_id"]
    modes = {m["id"]: m for m in await c.modes()}
    for index, speed, bypass, off in [
        (1, 3, 1, False),
        (2, 3, 0, False),
        (4, 1, 0, True),
    ]:
        mode = modes[saved[index]["mode_id"]]
        assert (mode["speed"], mode["bypass"], mode["off"], mode["mode"]) == (
            speed,
            bypass,
            off,
            "manual",
        )
    await c.edit_day(10, 2, rows, revision(changed))
    assert (await c.week(10))["d2"] == saved
    assert [endpoint for endpoint, _ in writes] == [
        "modes",
        "modes",
        "modes",
        "edit-schedule",
        "edit-schedule",
    ]


async def test_invalid_direct_schedule_writes_nothing(cloud):
    c, writes = cloud
    original = await c.week(10)
    rows = [{"time": 0, "speed": 3, "bypass": True}]
    with pytest.raises(DeviceError, match="Schedule changed"):
        await c.edit_day(10, 1, rows, "stale")
    with pytest.raises(DeviceError):
        await c.edit_day(10, 1, [*rows, {"time": 420, "mode": 999}], revision(original))
    with pytest.raises(DeviceError):
        await c.edit_day(
            10, 1, [{"time": 0, "speed": 3, "bypass": 1}], revision(original)
        )
    assert writes == []


async def test_retry_after_partial_schedule_save_reuses_created_modes(
    cloud, monkeypatch
):
    c, writes = cloud
    original = await c.week(10)
    rows = [{"time": 0, "speed": 2, "bypass": True}]
    write = c.api.write
    failed = False

    async def fail_once(endpoint, payload):
        nonlocal failed
        if endpoint == "edit-schedule" and not failed:
            failed = True
            raise ApiError("Simulated failure after mode creation")
        return await write(endpoint, payload)

    monkeypatch.setattr(c.api, "write", fail_once)
    with pytest.raises(ApiError, match="Schedule write was not confirmed"):
        await c.edit_day(10, 1, rows, revision(original))
    assert await c.week(10) == original
    await c.edit_day(10, 1, rows, revision(original))
    assert [endpoint for endpoint, _ in writes] == ["modes", "edit-schedule"]


@pytest.mark.parametrize("cloud", ["legacy_mode"], indirect=True)
async def test_mode_creation_is_confirmed_from_readback_and_reused(cloud):
    c, writes = cloud
    rows = [{"time": 0, "speed": 1, "bypass": False}]
    await c.edit_day(10, 1, rows, revision(await c.week(10)))
    week = await c.week(10)
    await c.edit_day(10, 2, rows, revision(week))
    assert (await c.week(10))["d2"] == week["d1"]
    assert [endpoint for endpoint, _ in writes] == [
        "modes",
        "edit-schedule",
        "edit-schedule",
    ]


@pytest.mark.parametrize(
    "cloud", ["zero_off_speed", "null_off_speed", "off_flag_omitted"], indirect=True
)
async def test_save_and_copy_off_schedule_when_cloud_normalizes_speed(cloud):
    c, writes = cloud
    rows = [{"time": 0, "mode": 20}, {"time": 1320, "speed": 0, "bypass": False}]
    await c.edit_day(10, 1, rows, revision(await c.week(10)))

    week = await c.week(10)
    result = await c.edit_days(10, [3, 5], rows, revision(week))

    assert result["saved_days"] == [3, 5]
    mode = next(mode for mode in await c.modes() if mode["name"] == "HA Schedule 0-0")
    after = await c.week(10)
    assert (
        after["d1"]
        == after["d3"]
        == after["d5"]
        == [
            {"time": 0, "mode_id": 20},
            {"time": 1320, "mode_id": mode["id"]},
        ]
    )
    assert [endpoint for endpoint, _ in writes] == [
        "modes",
        "edit-schedule",
        "edit-schedule",
        "edit-schedule",
    ]


@pytest.mark.parametrize("cloud", ["saved_off_mode"], indirect=True)
async def test_edit_existing_monday_with_off_mode_that_has_no_off_flag(cloud):
    c, writes = cloud
    before = await c.week(10)
    rows = [
        {"time": 0, "speed": 3, "bypass": False},
        {"time": 480, "speed": 2, "bypass": False},
        {"time": 720, "speed": 0, "bypass": False},
        {"time": 960, "speed": 2, "bypass": False},
        {"time": 1260, "speed": 3, "bypass": False},
    ]
    assert await c.edit_days(10, [1], rows, revision(before)) == {"saved_days": [1]}

    assert await c.week(10) == {
        **before,
        "d1": [
            {"time": 0, "mode_id": 22},
            {"time": 480, "mode_id": 21},
            {"time": 720, "mode_id": 23},
            {"time": 960, "mode_id": 21},
            {"time": 1260, "mode_id": 22},
        ],
    }
    assert [endpoint for endpoint, _ in writes] == ["edit-schedule"]


async def test_batch_copy_validates_all_destinations_and_creates_modes_once(cloud):
    c, writes = cloud
    rows = [{"time": 0, "speed": 2, "bypass": True}]
    before = await c.week(10)
    with pytest.raises(DeviceError):
        await c.edit_days(10, [1, 7], rows, revision(before))
    assert writes == []
    result = await c.edit_days(10, [1, 3, 5], rows, revision(before))
    after = await c.week(10)
    assert result["saved_days"] == [1, 3, 5]
    assert after["d1"] == after["d3"] == after["d5"]
    assert all(after[f"d{i}"] == before[f"d{i}"] for i in (0, 2, 4, 6))
    assert [endpoint for endpoint, _ in writes] == [
        "modes",
        "edit-schedule",
        "edit-schedule",
        "edit-schedule",
    ]


async def test_batch_copy_stops_and_reports_days_already_saved(cloud, monkeypatch):
    c, writes = cloud
    before = await c.week(10)
    write = c.api.write

    async def fail_second(endpoint, payload):
        if endpoint == "edit-schedule" and payload["wday"] == 3:
            raise ApiError("Simulated unconfirmed write")
        return await write(endpoint, payload)

    monkeypatch.setattr(c.api, "write", fail_second)
    rows = [{"time": 0, "speed": 1, "bypass": False}]
    with pytest.raises(ScheduleError) as result:
        await c.edit_days(10, [1, 3, 5], rows, revision(before))
    assert result.value.code == "scheduleWriteUnconfirmed"
    assert result.value.saved_days == [1]
    assert [payload["wday"] for path, payload in writes if path == "edit-schedule"] == [
        1
    ]


async def test_batch_limit_is_checked_before_creating_any_mode(cloud):
    c, writes = cloud
    rows = [{"time": time, "speed": 2, "bypass": False} for time in range(50)]
    with pytest.raises(DeviceError, match="Maximum 150"):
        await c.edit_days(10, [1, 3, 5], rows, revision(await c.week(10)))
    assert not writes
