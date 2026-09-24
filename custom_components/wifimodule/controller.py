"""Validated building-wide operations. No arbitrary API passthrough."""

import asyncio
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from .api import DeviceError
from .models import (
    Heartbeat,
    integer,
    mode_payload,
    name,
    normalize_building,
    override_until,
    record,
    revision,
    schedule_rows,
)


class Controller:
    def __init__(self, api, building_id, unit_ids, timezone):
        self.api, self.building_id = api, building_id
        self.unit_ids = frozenset(unit_ids)
        self.timezone = ZoneInfo(timezone)
        self.lock = asyncio.Lock()
        self.heartbeats = {}
        self.data = None
        self.duration = 30

    async def poll(self):
        raw = record(await self.api.read("status", "status"), self.building_id)
        self.data = normalize_building(raw)
        for unit in self.data["units"]:
            self.heartbeats.setdefault(unit["id"], Heartbeat()).observe(
                unit.get("last_comm")
            )
        return self.data

    @property
    def ready(self):
        return (
            self.data is not None
            and bool(self.unit_ids)
            and {u["id"] for u in self.data["units"]} == self.unit_ids
            and all(self.heartbeats[u].fresh for u in self.unit_ids)
        )

    async def ensure_membership(self, fresh=False):
        await self.poll()
        if {u["id"] for u in self.data["units"]} != self.unit_ids or not self.unit_ids:
            raise DeviceError(
                "Building membership changed; reconfigure the integration"
            )
        if fresh and not self.ready:
            raise DeviceError("Waiting for fresh device communication")

    async def profiles(self):
        return await self.api.read(f"profiles?building={self.building_id}", "profiles")

    async def modes(self):
        return await self.api.read(f"modes?building={self.building_id}", "modes")

    async def week(self, profile_id):
        record(await self.profiles(), profile_id)
        result = await self.api.read(
            f"schedule?building={self.building_id}&profile={profile_id}", "schedule"
        )
        if not isinstance(result, dict) or any(
            not isinstance(result.get(f"d{d}"), list) for d in range(7)
        ):
            raise DeviceError("Invalid weekly schedule")
        return result

    def _current(self, field, register):
        if self.data.get("manual_active") is True:
            value = self.data.get(field)
            if value is not None:
                return value
        values = {u["values"].get(register) for u in self.data["units"]}
        if len(values) != 1 or None in values:
            raise DeviceError("Units disagree; specify all control values explicitly")
        return values.pop()

    async def control(
        self, *, speed=None, bypass=None, mode=None, duration=None, schedule=False
    ):
        async with self.lock:
            await self.poll()
            if not self.ready:
                raise DeviceError(
                    "Waiting for fresh communication or building membership changed"
                )
            if schedule:
                payload = {"building": self.building_id, "manual": False}
            else:
                if speed is None:
                    if self.data.get("manual_active") is True:
                        speed = self.data.get("manual_speed")
                    else:
                        levels = {
                            0
                            if u["values"].get("pwr") == 0
                            else 8
                            if u["values"].get("bst") == 1
                            else u["values"].get("spe")
                            for u in self.data["units"]
                        }
                        if len(levels) != 1:
                            raise DeviceError("Units have different speeds")
                        speed = levels.pop()
                speed = integer(speed, 0, 8)
                if bypass is None:
                    raw = self._current("manual_bypass", "byp")
                    if raw not in (0, 1):
                        raise DeviceError("Unknown bypass")
                    bypass = bool(raw)
                if type(bypass) is not bool:
                    raise DeviceError("Invalid bypass")
                if mode is None:
                    if self.data.get("manual_active") is True:
                        mode = self.data.get("manual_mode")
                    else:
                        raw = self._current("manual_mode", "moa")
                        mode = {0: "manual", 1: "auto"}.get(raw)
                if mode not in ("manual", "auto"):
                    raise DeviceError("Unknown control mode")
                minutes = integer(
                    self.duration if duration is None else duration, 0, 10080
                )
                if speed == 8 and not 1 <= minutes <= 60:
                    raise DeviceError(
                        "Boost requires a duration between 1 and 60 minutes"
                    )
                until = override_until(minutes, self.timezone)
                payload = {
                    "building": self.building_id,
                    "manual": True,
                    "speed": speed,
                    "bypass": bypass,
                    "mode": mode,
                    "switch": until,
                }
            return await self.api.write("unit-config", payload)

    async def activate(self, profile_id):
        async with self.lock:
            await self.ensure_membership(fresh=True)
            record(await self.profiles(), profile_id)
            return await self.api.write(
                "profiles",
                {
                    "op": "activate",
                    "data": {"profile": profile_id, "building": self.building_id},
                },
            )

    async def edit_day(self, profile_id, day, rows, expected_revision):
        async with self.lock:
            await self.ensure_membership()
            integer(day, 0, 6)
            week = await self.week(profile_id)
            if revision(week) != expected_revision:
                raise DeviceError("Schedule changed. Reload before saving")
            rows = schedule_rows(rows, {m["id"] for m in await self.modes()})
            if (
                len(rows)
                + sum(
                    len(v)
                    for k, v in week.items()
                    if k != f"d{day}" and k in {f"d{d}" for d in range(7)}
                )
                > 150
            ):
                raise DeviceError("Maximum 150 weekly changes")
            return await self.api.write(
                "edit-schedule",
                {
                    "building": self.building_id,
                    "profile": profile_id,
                    "wday": day,
                    "schedule": rows,
                },
            )

    async def mutate_profile(self, operation, data):
        if operation not in ("add", "edit", "delete"):
            raise DeviceError("Invalid operation")
        async with self.lock:
            await self.ensure_membership()
            existing = await self.profiles()
            item = record(existing, data.get("id")) if operation != "add" else {}
            if operation == "delete":
                await self.poll()
                if self.data.get("profile_id") == item["id"]:
                    raise DeviceError(
                        "Activate another profile before deleting this one"
                    )
                body = {"id": item["id"]}
            else:
                title = name(data.get("name"))
                if any(
                    p["name"] == title and p["id"] != item.get("id") for p in existing
                ):
                    raise DeviceError("Name already exists")
                body = (
                    {**item, "name": title}
                    if item
                    else {"name": title, "building_id": self.building_id}
                )
            return await self.api.write("profiles", {"op": operation, "data": body})

    async def mutate_mode(self, operation, data):
        if operation not in ("add", "edit", "delete"):
            raise DeviceError("Invalid operation")
        async with self.lock:
            await self.ensure_membership()
            existing = await self.modes()
            item = record(existing, data.get("id")) if operation != "add" else {}
            if operation == "delete":
                for profile in await self.profiles():
                    week = await self.week(profile["id"])
                    if any(
                        r.get("mode_id", r.get("mode")) == item["id"]
                        for rows in week.values()
                        for r in rows
                    ):
                        raise DeviceError("Mode is used by a schedule")
                body = {"id": item["id"]}
            else:
                body = mode_payload(
                    data, identity=item.get("id"), building=self.building_id
                )
                if any(
                    m["name"] == body["name"] and m["id"] != item.get("id")
                    for m in existing
                ):
                    raise DeviceError("Name already exists")
            return await self.api.write("modes", {"op": operation, "data": body})

    async def history(self, unit_id, start=None, end=None):
        if integer(unit_id) not in self.unit_ids:
            raise DeviceError("Foreign unit")
        await self.poll()
        record(self.data["units"], unit_id)
        query = {"unit": unit_id}
        if start is not None or end is not None:
            try:
                first, last = (
                    datetime.strptime(v, "%Y-%m-%d %H:%M:%S") for v in (start, end)
                )
            except ValueError, TypeError:
                raise DeviceError("Invalid history date range") from None
            if not 0 < (last - first).total_seconds() <= 366 * 86400:
                raise DeviceError("History range must be within 366 days")
            query.update({"from": start, "to": end})
        return await self.api.read("chart?" + urlencode(query), "chart")
