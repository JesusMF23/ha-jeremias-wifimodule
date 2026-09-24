from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.wifimodule.api import DeviceError
from custom_components.wifimodule.models import (
    integer,
    mode_payload,
    normalize_building,
    override_until,
    revision,
    schedule_rows,
)


@pytest.mark.parametrize("value", [True, -1, 2.0, "1"])
def test_ids_are_strict(value):
    with pytest.raises(DeviceError):
        integer(value)


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"time": 1, "mode": 1}],
        [{"time": 0, "mode": 2}],
        [{"time": 0, "mode": 1}, {"time": 0, "mode": 1}],
        [{"time": 0, "mode": 1}, {"time": 1440, "mode": 1}],
    ],
)
def test_invalid_days_fail_closed(rows):
    with pytest.raises(DeviceError):
        schedule_rows(rows, {1})


def test_revision_ignores_names_but_detects_other_day_changes():
    week = {"d1": [{"time": 0, "mode_id": 1, "name": "Old"}]}
    same = {"d1": [{"time": 0, "mode": 1, "name": "New"}]}
    assert revision(week) == revision(same)
    same["d2"] = [{"time": 0, "mode": 1}]
    assert revision(week) != revision(same)


def test_boost_mode_encodes_website_flags():
    payload = mode_payload(
        {"name": "Boost", "speed": 8, "bypass": False, "mode": "manual"}, building=1
    )
    assert payload["boost"] and not payload["off"] and payload["speed"] == 7


def test_dst_expiry_uses_elapsed_time_and_rejects_ambiguous_hour():
    tz = ZoneInfo("Europe/Madrid")
    with pytest.raises(DeviceError):
        override_until(30, tz, datetime(2026, 10, 25, 0, 45, tzinfo=UTC))
    assert (
        override_until(90, tz, datetime(2026, 10, 25, 0, 45, tzinfo=UTC))
        == "2026-10-25 03:15"
    )
    assert (
        override_until(30, tz, datetime(2026, 3, 29, 0, 45, tzinfo=UTC))
        == "2026-03-29 03:15"
    )


@pytest.mark.parametrize("units", [[None], [{"id": True}]])
def test_invalid_unit_shapes(units):
    with pytest.raises(DeviceError):
        normalize_building({"id": 1, "units": units})
