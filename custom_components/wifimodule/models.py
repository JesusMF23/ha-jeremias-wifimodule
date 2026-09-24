"""Pure validation and protocol transformations."""

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from time import monotonic

from .api import DeviceError
from .const import STALE_SECONDS


def integer(value, low=1, high=2**31 - 1):
    if type(value) is not int or not low <= value <= high:
        raise DeviceError("Invalid integer")
    return value


def record(items, identity):
    integer(identity)
    if not isinstance(items, list):
        raise DeviceError("Invalid collection")
    matches = [v for v in items if isinstance(v, dict) and v.get("id") == identity]
    if len(matches) != 1:
        raise DeviceError("Identifier is missing or ambiguous")
    return matches[0]


def name(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 100:
        raise DeviceError("Name must contain 1–100 characters")
    return value.strip()


def registers(raw):
    try:
        result = {}
        for item in raw.split(","):
            key, value = item.split(":")
            if not key or key in result:
                raise ValueError
            result[key] = int(value)
        return result
    except AttributeError, TypeError, ValueError:
        return {}


def normalize_building(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get("units"), list):
        raise DeviceError("Invalid building status")
    integer(raw.get("id"))
    units = []
    seen = set()
    for unit in raw["units"]:
        if not isinstance(unit, dict):
            raise DeviceError("Invalid unit")
        identity = integer(unit.get("id"))
        if identity in seen:
            raise DeviceError("Duplicate unit")
        seen.add(identity)
        units.append({**unit, "values": registers(unit.get("status"))})
    return {**raw, "units": units}


class Heartbeat:
    def __init__(self, clock=monotonic):
        self.clock, self.stamp, self.advanced = clock, None, None

    def observe(self, stamp):
        try:
            datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
        except ValueError, TypeError:
            self.advanced = None
            return
        if self.stamp is not None:
            if stamp > self.stamp:
                self.advanced = self.clock()
            elif stamp < self.stamp:
                self.advanced = None
        self.stamp = stamp

    @property
    def fresh(self):
        return (
            self.advanced is not None and self.clock() - self.advanced < STALE_SECONDS
        )


def schedule_rows(rows, mode_ids):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 150:
        raise DeviceError("A day must contain 1–150 changes")
    result = []
    previous = -1
    for item in rows:
        if not isinstance(item, dict):
            raise DeviceError("Invalid schedule row")
        minute = integer(item.get("time"), 0, 1439)
        mode = integer(item.get("mode", item.get("mode_id")))
        if minute <= previous or mode not in mode_ids:
            raise DeviceError(
                "Times must increase and modes must belong to this building"
            )
        result.append({"time": minute, "mode": mode})
        previous = minute
    if result[0]["time"] != 0:
        raise DeviceError("The first change must start at 00:00")
    return result


def revision(week):
    normalized = {
        f"d{d}": [
            {"time": r["time"], "mode": r.get("mode_id", r.get("mode"))}
            for r in week.get(f"d{d}", [])
        ]
        for d in range(7)
    }
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()


def mode_payload(data, identity=None, building=None):
    speed = integer(data.get("speed"), 0, 8)
    color = data.get("color", "#b4c7dc")
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise DeviceError("Invalid mode color")
    if (
        data.get("mode") not in ("manual", "auto")
        or type(data.get("bypass")) is not bool
    ):
        raise DeviceError("Invalid mode or bypass")
    result = {
        "name": name(data.get("name")),
        "color": color,
        "speed": min(7, max(1, speed)),
        "off": speed == 0,
        "boost": speed == 8,
        "bypass": int(data["bypass"]),
        "mode": data["mode"],
    }
    result.update(
        {"id": identity} if identity is not None else {"building_id": building}
    )
    return result


def override_until(minutes, timezone, now=None):
    """Calculate elapsed duration, rejecting ambiguous offset-free wire times."""
    if minutes == 0:
        return "never"
    expiry = (
        (now or datetime.now(UTC)).astimezone(UTC) + timedelta(minutes=minutes)
    ).astimezone(timezone)
    if expiry.replace(fold=0).utcoffset() != expiry.replace(fold=1).utcoffset():
        raise DeviceError(
            "Expiry falls in a repeated local hour; choose another duration"
        )
    return expiry.strftime("%Y-%m-%d %H:%M")
