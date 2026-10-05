"""Deterministic ventilation demand calculation; no I/O or HA dependencies."""

from dataclasses import asdict, dataclass, fields
from math import ceil, exp, isfinite

KINDS = ("co2", "tvoc", "humidity", "aqi")
UNITS = {"co2": ("ppm",), "tvoc": ("ppb",), "humidity": ("%",), "aqi": (None, "")}
# default, minimum, maximum, step; shared by backend validation and UI.
PARAMETERS = {
    "min_speed": (1, 1, 7, 1),
    "max_speed": (7, 1, 7, 1),
    "co2_target": (800, 300, 5000, 10),
    "co2_full": (1500, 400, 10000, 10),
    "tvoc_target": (300, 0, 5000, 10),
    "tvoc_full": (1000, 1, 10000, 10),
    "humidity_target": (60, 20, 95, 1),
    "humidity_full": (75, 21, 100, 1),
    "aqi_target": (50, 0, 499, 1),
    "aqi_full": (200, 1, 500, 1),
    "hysteresis": (5, 0, 20, 1),
    "rise_seconds": (30, 10, 300, 10),
    "fall_seconds": (300, 30, 3600, 10),
    "filter_rise_seconds": (30, 0, 300, 10),
    "filter_fall_seconds": (180, 0, 1800, 10),
    "minimum_interval": (60, 0, 600, 10),
    "stale_seconds": (900, 60, 7200, 60),
}


@dataclass(frozen=True)
class Settings:
    min_speed: int = 1
    max_speed: int = 7
    co2_target: int = 800
    co2_full: int = 1500
    tvoc_target: int = 300
    tvoc_full: int = 1000
    humidity_target: int = 60
    humidity_full: int = 75
    aqi_target: int = 50
    aqi_full: int = 200
    hysteresis: int = 5
    rise_seconds: int = 30
    fall_seconds: int = 300
    filter_rise_seconds: int = 30
    filter_fall_seconds: int = 180
    minimum_interval: int = 60
    stale_seconds: int = 900

    @classmethod
    def from_dict(cls, values):
        if set(values) - {f.name for f in fields(cls)}:
            raise ValueError("Unknown setting")
        for key, value in values.items():
            _, low, high, _ = PARAMETERS[key]
            if (
                type(value) not in (int, float)
                or not isfinite(value)
                or not low <= value <= high
                or int(value) != value
            ):
                raise ValueError("Invalid setting: " + key)
        result = cls(**{k: int(v) for k, v in values.items()})
        if (
            result.min_speed > result.max_speed
            or result.fall_seconds < result.rise_seconds
            or result.filter_fall_seconds < result.filter_rise_seconds
        ):
            raise ValueError("Invalid limits or timing")
        for kind in KINDS:
            if getattr(result, kind + "_target") >= getattr(result, kind + "_full"):
                raise ValueError("Full demand must exceed target")
        return result

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Reading:
    entity_id: str
    name: str
    kind: str
    value: object
    unit: str | None
    age: float

    def numeric(self, max_age):
        if self.kind not in UNITS or self.unit not in UNITS[self.kind]:
            return None
        try:
            value = float(self.value)
        except TypeError, ValueError:
            return None
        high = {"co2": 100000, "tvoc": 1000000, "humidity": 100, "aqi": 500}[self.kind]
        low = 250 if self.kind == "co2" else 0
        if (
            not isfinite(value)
            or not low <= value <= high
            or not isfinite(self.age)
            or not 0 <= self.age <= max_age
        ):
            return None
        return value


@dataclass
class Decision:
    status: str
    target: int | None = None
    command: int | None = None
    demand: float = 0
    source: Reading | None = None
    invalid: tuple = ()
    wait_seconds: int = 0


class DemandEngine:
    def __init__(self, settings):
        self.settings = settings
        self.filters = {}
        self.pending = None
        self.pending_since = 0
        self.last_sent = float("-inf")

    def sent(self, speed, now, *, changed=True):
        self.last_sent = now
        if changed:
            self.pending = None

    def reset_pending(self):
        self.pending = None

    def evaluate(self, readings, current, now):
        s = self.settings
        valid, invalid = [], []
        for r in readings:
            value = r.numeric(s.stale_seconds)
            if value is None:
                invalid.append(r.entity_id)
                self.filters.pop(r.entity_id, None)
                continue
            low, high = getattr(s, r.kind + "_target"), getattr(s, r.kind + "_full")
            raw = min(1.0, max(0.0, (value - low) / (high - low)))
            prev, stamp = self.filters.get(r.entity_id, (raw, now))
            tau = s.filter_rise_seconds if raw >= prev else s.filter_fall_seconds
            alpha = 1 if tau == 0 else 1 - exp(-max(0, now - stamp) / tau)
            filtered = prev + alpha * (raw - prev)
            # Exponential decay never reaches zero. Settle below 0.1% only
            # while the actual reading is at/below its configured target.
            if raw == 0 and filtered < 0.001:
                filtered = 0.0
            self.filters[r.entity_id] = (filtered, now)
            valid.append((filtered, r))
        if not valid:
            self.reset_pending()
            return Decision("no_data", invalid=tuple(invalid))
        demand, source = max(valid, key=lambda item: item[0])
        span = s.max_speed - s.min_speed
        target = s.min_speed + ceil(round(demand * span, 9))
        if span and s.min_speed < current <= s.max_speed and target < current:
            boundary = (current - s.min_speed - 1) / span
            # At zero demand the minimum remains reachable even with hysteresis.
            if demand > max(0.0, boundary - s.hysteresis / 100):
                target = current
        result = Decision(
            "partial_data" if invalid else "holding",
            target=target,
            demand=demand,
            source=source,
            invalid=tuple(invalid),
        )
        if (invalid and target < current) or target == current:
            self.reset_pending()
            return result
        candidate = (
            target
            if target > current
            else max(s.min_speed, min(s.max_speed, current - 1))
        )
        if self.pending != candidate:
            self.pending, self.pending_since = candidate, now
        delay = s.rise_seconds if candidate > current else s.fall_seconds
        remaining = max(
            delay - (now - self.pending_since),
            s.minimum_interval - (now - self.last_sent),
            0,
        )
        result.wait_seconds = ceil(remaining)
        result.status = "rising" if candidate > current else "falling"
        if remaining == 0:
            result.command = candidate
        return result
