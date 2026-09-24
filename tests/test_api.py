"""Real localhost HTTP, private cookie jars and observed response contracts."""

from collections import Counter

import pytest
from aiohttp import ClientSession, CookieJar, web

from custom_components.wifimodule import api as module
from custom_components.wifimodule.api import ApiError, AuthError, WifiModuleApi


@pytest.fixture
async def server(monkeypatch):
    calls = Counter()
    state = {"reject": 0, "failure": None}

    async def handle(request):
        endpoint = request.match_info["endpoint"]
        calls[endpoint] += 1
        if endpoint == "login":
            body = await request.json()
            if body != {"email": "test@example.invalid", "password": "test-only"}:
                return web.json_response({"msg": "failed"})
            response = web.json_response({"msg": "success"})
            response.set_cookie("session", "local-test-session", httponly=True)
            return response
        assert request.cookies.get("session") == "local-test-session"
        if state["reject"]:
            state["reject"] -= 1
            return web.json_response({"err": "permissions"})
        if state["failure"] == "redirect":
            return web.Response(status=302, headers={"Location": "/api/trap"})
        if state["failure"] == "json":
            return web.Response(text="<html>error</html>")
        if state["failure"] == "large":
            return web.Response(body=b"x" * 1_000_001)
        if state["failure"] == "http":
            return web.Response(status=500)
        if endpoint == "unit-config":
            assert await request.json() == {"building": 1, "manual": False}
            return web.json_response({"msg": "success"})
        return web.json_response({"msg": "status", "status": [{"id": 1}]})

    app = web.Application()
    app.router.add_route("*", "/api/{endpoint}", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    monkeypatch.setattr(module, "BASE_URL", f"http://127.0.0.1:{port}/api/")
    async with ClientSession(cookie_jar=CookieJar(unsafe=True)) as session:
        yield WifiModuleApi(session, "test@example.invalid", "test-only"), calls, state
    await runner.cleanup()


async def test_login_cookie_and_control(server):
    api, calls, _ = server
    assert await api.read("status", "status") == [{"id": 1}]
    assert await api.write("unit-config", {"building": 1, "manual": False}) == {
        "msg": "success"
    }
    assert calls["login"] == 1


async def test_renew_once_on_explicit_rejection(server):
    api, calls, state = server
    state["reject"] = 1
    await api.read("status", "status")
    assert calls["login"] == 2 and calls["status"] == 2


async def test_repeated_auth_rejection_is_bounded(server):
    api, calls, state = server
    state["reject"] = 3
    with pytest.raises(AuthError):
        await api.read("status", "status")
    assert calls["login"] == 2 and not api.authenticated


@pytest.mark.parametrize("failure", ["redirect", "json", "large", "http"])
async def test_ambiguous_writes_not_retried_or_redirected(server, failure):
    api, calls, state = server
    state["failure"] = failure
    with pytest.raises(ApiError):
        await api.write("unit-config", {"building": 1, "manual": False})
    assert calls["unit-config"] == 1 and calls["trap"] == 0
