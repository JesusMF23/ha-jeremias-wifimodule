"""Demand control acceptance tests with deterministic time and fictional sensors."""

import math

import pytest

from custom_components.wifimodule.demand import DemandEngine, Reading, Settings


def reading(value, kind="co2", entity="sensor.bedroom", unit="ppm", age=0):
    return Reading(entity, entity, kind, value, unit, age)


def settings(**kwargs):
    return Settings.from_dict(
        {
            "rise_seconds": 30,
            "fall_seconds": 300,
            "filter_rise_seconds": 0,
            "filter_fall_seconds": 0,
            "minimum_interval": 0,
            **kwargs,
        }
    )


def test_worst_normalized_demand_wins_not_largest_raw_value():
    e = DemandEngine(settings())
    r = e.evaluate(
        [reading(1000), reading(1000, "tvoc", "sensor.kitchen", "ppb")], 2, 0
    )
    assert r.source.entity_id == "sensor.kitchen" and r.target == 7
    assert r.command is None
    assert (
        e.evaluate(
            [reading(1000), reading(1000, "tvoc", "sensor.kitchen", "ppb")], 2, 30
        ).command
        == 7
    )


def test_fall_is_slow_and_only_one_step():
    e = DemandEngine(settings())
    assert e.evaluate([reading(600)], 7, 0).command is None
    assert e.evaluate([reading(600)], 7, 299).command is None
    assert e.evaluate([reading(600)], 7, 300).command == 6
    e.sent(6, 300)
    assert e.evaluate([reading(600)], 6, 301).command is None
    assert e.evaluate([reading(600)], 6, 601).command == 5


def test_hysteresis_holds_near_downward_boundary():
    e = DemandEngine(settings())
    # speed 4 -> 3 boundary is 1/3 demand: 1033.33 ppm; margin is 5%.
    assert e.evaluate([reading(1020)], 4, 0).target == 4
    assert e.evaluate([reading(1020)], 4, 900).command is None
    e.evaluate([reading(950)], 4, 901)
    assert e.evaluate([reading(950)], 4, 1201).command == 3


def test_delay_resets_when_demand_recovers():
    e = DemandEngine(settings())
    e.evaluate([reading(1500)], 2, 0)
    e.evaluate([reading(600)], 2, 20)
    assert e.evaluate([reading(1500)], 2, 31).command is None
    assert e.evaluate([reading(1500)], 2, 61).command == 7


@pytest.mark.parametrize(
    "value,unit,age",
    [
        (math.nan, "ppm", 0),
        (math.inf, "ppm", 0),
        (-1, "ppm", 0),
        ("unavailable", "ppm", 0),
        (900, "ppb", 0),
        (900, "ppm", 901),
    ],
)
def test_invalid_or_stale_values_never_become_zero(value, unit, age):
    e = DemandEngine(settings())
    r = e.evaluate([reading(value, unit=unit, age=age)], 4, 0)
    assert r.command is None and r.status == "no_data" and len(r.invalid) == 1


def test_mass_tvoc_is_rejected_no_unjustified_ppb_conversion():
    e = DemandEngine(settings())
    assert e.evaluate([reading(500, "tvoc", unit="µg/m³")], 4, 0).status == "no_data"


def test_partial_sensor_loss_blocks_reductions_but_allows_increases():
    e = DemandEngine(settings())
    bad = reading("unknown", entity="sensor.missing")
    e.evaluate([reading(600), bad], 5, 0)
    r = e.evaluate([reading(600), bad], 5, 400)
    assert r.command is None and r.status == "partial_data"
    e.evaluate([reading(1500), bad], 5, 401)
    assert e.evaluate([reading(1500), bad], 5, 431).command == 7


def test_limits_and_minimum_interval():
    e = DemandEngine(settings(min_speed=2, max_speed=5, minimum_interval=60))
    e.sent(3, 0)
    assert e.evaluate([reading(2000)], 3, 1).target == 5
    assert e.evaluate([reading(2000)], 3, 31).command is None
    assert e.evaluate([reading(2000)], 3, 61).command == 5
    assert (
        DemandEngine(settings(min_speed=4, max_speed=4))
        .evaluate([reading(600)], 4, 0)
        .target
        == 4
    )


def test_asymmetric_filter_uses_elapsed_time():
    e = DemandEngine(settings(filter_rise_seconds=30, filter_fall_seconds=180))
    e.evaluate([reading(800)], 1, 0)
    up = e.evaluate([reading(1500)], 1, 30).demand
    down = e.evaluate([reading(800)], 1, 60).demand
    assert 0.63 < up < 0.64 and 0.53 < down < 0.54


def test_filter_removed_on_sensor_loss():
    e = DemandEngine(settings(filter_rise_seconds=30, filter_fall_seconds=180))
    e.evaluate([reading(1500)], 7, 0)
    e.evaluate([reading("unknown")], 7, 30)
    assert e.evaluate([reading(800)], 7, 40).demand == 0


def test_filtered_low_demand_eventually_reaches_minimum():
    e = DemandEngine(Settings())
    current = 7
    e.evaluate([reading(1500)], current, 0)
    for now in range(10, 7200, 10):
        decision = e.evaluate([reading(600)], current, now)
        if decision.command is not None:
            current = decision.command
            e.sent(current, now)
    assert current == 1


@pytest.mark.parametrize(
    "values",
    [
        {"min_speed": 5, "max_speed": 4},
        {"co2_target": 1500, "co2_full": 800},
        {"rise_seconds": math.nan},
        {"min_speed": 1.2},
        {"unexpected": 2},
        {"fall_seconds": 10, "rise_seconds": 30},
    ],
)
def test_settings_reject_invalid_ranges_and_unknown_keys(values):
    with pytest.raises(ValueError):
        Settings.from_dict(values)


def test_optional_zero_minimum_stops_only_after_slow_confirmation():
    e = DemandEngine(settings(min_speed=0))
    assert Settings().min_speed == 1  # Existing installations retain ventilation.
    assert e.evaluate([reading(600)], 1, 0).target == 0
    assert e.evaluate([reading(600)], 1, 299).command is None
    assert e.evaluate([reading(600)], 1, 300).command == 0


def test_zero_minimum_restarts_on_valid_demand_and_never_on_missing_data():
    e = DemandEngine(settings(min_speed=0))
    bad = reading("unavailable", entity="sensor.other")
    assert e.evaluate([reading(600), bad], 1, 0).command is None
    assert e.evaluate([reading(600), bad], 1, 600).command is None
    assert e.evaluate([bad], 0, 610).target is None
    assert e.evaluate([reading(1000)], 0, 620).target == 2
    assert e.evaluate([reading(1000)], 0, 649).command is None
    assert e.evaluate([reading(1000)], 0, 650).command == 2
