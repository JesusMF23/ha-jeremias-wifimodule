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
        if minute <= previous:
            raise DeviceError(
                "Times must increase and modes must belong to this building"
            )
        if "speed" in item or "bypass" in item:
            if (
                set(item) != {"time", "speed", "bypass"}
                or type(item["bypass"]) is not bool
            ):
                raise DeviceError("Invalid fixed speed or bypass")
            row = {"speed": integer(item["speed"], 0, 7), "bypass": item["bypass"]}
        else:
            mode = integer(item.get("mode", item.get("mode_id")))
            if mode not in mode_ids:
                raise DeviceError(
                    "Times must increase and modes must belong to this building"
                )
            row = {"mode": mode}
        result.append({"time": minute, **row})
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


def schedule_mode_name(speed, bypass):
    return f"HA Schedule {speed}-{int(bypass)}"


def _mode_flag(value):
    if value in (None, False, "0"):
        return False
    if value in (True, "1"):
        return True
    return None


def managed_schedule_mode(mode):
    """Recognize fixed speeds by both the reserved name and actual settings."""
    match = re.fullmatch(
        r"HA Schedule ([0-7])-([01])(?: \([0-9]+\))?",
        str(mode.get("name", "")),
    )
    if match is None:
        return None
    speed, bypass = int(match[1]), match[2] == "1"
    wire_speed = mode.get("speed")
    if (
        isinstance(wire_speed, str)
        and len(wire_speed) == 1
        and wire_speed in "01234567"
    ):
        wire_speed = int(wire_speed)
    # WifiModule can read back a saved Off mode as speed 0 without the write flag.
    wire_off = mode.get("off")
    off = (
        type(wire_speed) is int and wire_speed == 0
        if wire_off is None
        else _mode_flag(wire_off)
    )
    if (
        mode.get("mode") != "manual"
        or off is not (speed == 0)
        or _mode_flag(mode.get("boost")) is not False
        or _mode_flag(mode.get("bypass")) is not bypass
    ):
        return None
    # The off flag controls shutdown; the stored fan level is unused.
    if speed and (type(wire_speed) is not int or wire_speed != speed):
        return None
    return {"speed": speed, "bypass": bypass}


def override_until(minutes, timezone, now=None):
    """Calculate elapsed duration, rejecting ambiguous offset-free wire times."""
    if minutes == 0:
        return "never"
    expiry = (
        (now or datetime.now(UTC)).astimezone(UTC) + timedelta(minutes=minutes)
    ).astimezone(timezone)
    return override_expiry(expiry, timezone)


def override_expiry(expiry, timezone):
    """Serialize an absolute expiry without moving it during restart."""
    expiry = expiry.astimezone(timezone)
    if expiry.replace(fold=0).utcoffset() != expiry.replace(fold=1).utcoffset():
        raise DeviceError(
            "Expiry falls in a repeated local hour; choose another duration"
        )
    return expiry.strftime("%Y-%m-%d %H:%M")
