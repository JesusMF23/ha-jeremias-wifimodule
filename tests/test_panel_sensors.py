"""Catalogue uses actual device names and rejects stale/restored display values."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from homeassistant.core import State

from custom_components.wifimodule.panel_sensors import sensor_catalogue


def test_catalogue_groups_registered_devices_and_uses_regulation_validity():
    attrs = {"device_class": "carbon_dioxide", "unit_of_measurement": "ppm"}
    fresh = State("sensor.room_co2", "650", attrs)
    old = State(
        "sensor.old",
        "1500",
        attrs,
        last_reported=datetime.now(UTC) - timedelta(hours=1),
    )
    restored = State("sensor.restored", "900", {**attrs, "restored": True})
    wrong = State(
        "sensor.mass",
        "300",
        {
            "device_class": "volatile_organic_compounds_parts",
            "unit_of_measurement": "µg/m³",
        },
    )
    hass = Mock()
    hass.states.async_all.return_value = [fresh, old, restored, wrong]
    registry = Mock()
    registry.async_get.side_effect = lambda key: (
        SimpleNamespace(device_id="airq") if key == fresh.entity_id else None
    )
    devices = Mock()
    devices.async_get.return_value = SimpleNamespace(
        id="airq", name="Default", name_by_user="Upstairs"
    )
    with (
        patch(
            "custom_components.wifimodule.panel_sensors.er.async_get",
            return_value=registry,
        ),
        patch(
            "custom_components.wifimodule.panel_sensors.dr.async_get",
            return_value=devices,
        ),
    ):
        result = sensor_catalogue(hass, 900)
    assert result["tvoc"][0]["reason"] == "incompatible_unit"
    good, stale, restored = result["co2"]
    assert (good["zone_id"], good["zone"], good["value"], good["unit"]) == (
        "airq",
        "Upstairs",
        650,
        "ppm",
    )
    assert good["device_id"] == "airq"
    assert stale["device_id"] is None
    assert good["valid"]
    assert stale["value"] is restored["value"] is None
    assert not stale["valid"] and not restored["valid"]


def test_catalogue_accepts_unclassified_third_party_co2_and_explains_mass_voc():
    hass = Mock()
    hass.states.async_all.return_value = [
        State("sensor.third_party", "720", {"unit_of_measurement": "ppm"}),
        State(
            "sensor.mass_voc",
            "50",
            {
                "device_class": "volatile_organic_compounds",
                "unit_of_measurement": "µg/m³",
            },
        ),
    ]
    registry = Mock()
    registry.async_get.return_value = None
    with (
        patch(
            "custom_components.wifimodule.panel_sensors.er.async_get",
            return_value=registry,
        ),
        patch(
            "custom_components.wifimodule.panel_sensors.dr.async_get",
            return_value=registry,
        ),
    ):
        result = sensor_catalogue(hass, 900)
    assert result["co2"][0]["entity_id"] == "sensor.third_party"
    assert result["co2"][0]["compatible"]
    assert (
        next(x for x in result["tvoc"] if x["entity_id"] == "sensor.mass_voc")["reason"]
        == "incompatible_unit"
    )
    assert not next(x for x in result["tvoc"] if x["entity_id"] == "sensor.mass_voc")[
        "compatible"
    ]
