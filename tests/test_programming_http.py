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
from custom_components.wifimodule.api import ApiError, DeviceError, WifiModuleApi
from custom_components.wifimodule.controller import Controller
from custom_components.wifimodule.models import revision


@pytest.fixture
async def cloud(monkeypatch):
    modes = [{"id": 20, "name": "Low"}]
    profiles = [{"id": 10, "name": "Main"}]
    base = {f"d{i}": [{"time": 0, "mode_id": 20}] for i in range(7)}
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
        else:
            operation, data = body["op"], body["data"]
            collection = profiles if endpoint == "profiles" else modes
            if operation == "add":
                identity = max(item["id"] for item in collection) + 1
                collection.append({**data, "id": identity})
                if endpoint == "profiles":
                    weeks[identity] = deepcopy(base)
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
    with pytest.raises(ApiError, match="Simulated failure"):
        await c.edit_day(10, 1, rows, revision(original))
    assert await c.week(10) == original
    await c.edit_day(10, 1, rows, revision(original))
    assert [endpoint for endpoint, _ in writes] == ["modes", "edit-schedule"]
