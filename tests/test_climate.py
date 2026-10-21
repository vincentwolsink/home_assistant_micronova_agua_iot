"""Test the climate platform, also for devices without (successful) read data."""

from unittest.mock import MagicMock

import pytest

from tests.helpers import (
    build_device_from_fixture,
    build_device_without_values,
    load_component_module,
)

pytest.importorskip(
    "homeassistant.components.climate", reason="homeassistant is required"
)

climate = load_component_module("climate")
const = load_component_module("const")

REGISTER_MAP = {
    "power_set": {
        "reg_key": "power_set",
        "offset": 1,
        "mask": 255,
        "formula": "#",
        "formula_inverse": "#",
        "set_min": 1,
        "set_max": 3,
        "value_raw": "2",
        "value": 2,
        "enc_val": [
            {"value": 1, "description": "1", "lang": "ENG"},
            {"value": 2, "description": "2", "lang": "ENG"},
            {"value": 3, "description": "3", "lang": "ENG"},
        ],
    },
    "temp_air_get": {
        "reg_key": "temp_air_get",
        "offset": 2,
        "mask": 255,
        "formula": "#",
        "formula_inverse": "#",
        "value_raw": "20",
        "value": 20,
    },
    "temp_air_set": {
        "reg_key": "temp_air_set",
        "offset": 3,
        "mask": 255,
        "formula": "#",
        "formula_inverse": "#",
        "set_min": 15,
        "set_max": 30,
        "step": 1,
        "value_raw": "22",
        "value": 22,
    },
    "status_get": {
        "reg_key": "status_get",
        "offset": 4,
        "mask": 255,
        "formula": "#",
        "formula_inverse": "#",
        "value_raw": "0",
        "value": 0,
    },
}

CANALIZATION_REGISTER_MAP = {
    "canalization_1_set": {
        "reg_key": "canalization_1_set",
        "offset": 5,
        "mask": 255,
        "formula": "#",
        "formula_inverse": "#",
        "set_min": 0,
        "set_max": 2,
        "value_raw": "1",
        "value": 1,
        "enc_val": [
            {"value": 0, "description": "0", "lang": "ENG"},
            {"value": 1, "description": "1", "lang": "ENG"},
            {"value": 2, "description": "2", "lang": "ENG"},
        ],
    },
    "canalization_1_temp_air_set": {
        "reg_key": "canalization_1_temp_air_set",
        "offset": 6,
        "mask": 255,
        "formula": "#",
        "formula_inverse": "#",
        "set_min": 10,
        "set_max": 25,
        "value_raw": "20",
        "value": 20,
    },
}

WATER_REGISTER_MAP = {
    "temp_water_get": {
        "reg_key": "temp_water_get",
        "offset": 7,
        "mask": 255,
        "formula": "#",
        "formula_inverse": "#",
        "value_raw": "40",
        "value": 40,
    },
    "temp_water_set": {
        "reg_key": "temp_water_set",
        "offset": 8,
        "mask": 255,
        "formula": "#",
        "formula_inverse": "#",
        "set_min": 30,
        "set_max": 60,
        "value_raw": "45",
        "value": 45,
    },
}


class FakeUnits:
    """Minimal replacement for the Home Assistant unit configuration."""

    temperature_unit = "°C"


class FakeConfig:
    """Minimal replacement for the Home Assistant configuration."""

    units = FakeUnits()


class FakeHass:
    """Minimal replacement for the Home Assistant instance."""

    config = FakeConfig()


def make_canalization_description():
    """Return a canalization entity description."""
    return const.AguaIOTCanalizationEntityDescription(
        name="Canalization 1",
        key="canalization_1_set",
        key_temp_set="canalization_1_temp_air_set",
        key_temp_get="canalization_1_temp_air_get",
    )


def make_coordinator():
    """Return a coordinator mock of a successfully updated coordinator."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    return coordinator


class TestClimateWithoutDeviceData:
    """The device could not be read (yet), so no register values are available."""

    @pytest.fixture
    def entity(self, aguaiot_mock):
        device = build_device_without_values(aguaiot_mock, "test", REGISTER_MAP)
        return climate.AguaIOTAirDevice(make_coordinator(), device)

    def test_fan_modes_is_empty(self, entity):
        assert entity.fan_modes == []

    def test_fan_mode_is_none(self, entity):
        assert entity.fan_mode is None

    def test_min_max_temp_are_unknown(self, entity):
        assert entity.min_temp is None
        assert entity.max_temp is None

    def test_temperatures_are_unknown(self, entity):
        assert entity.current_temperature is None
        assert entity.target_temperature is None

    def test_target_temperature_step(self, entity):
        assert entity.target_temperature_step == 1

    def test_capability_attributes_do_not_raise(self, entity):
        entity.hass = FakeHass()
        attributes = entity.capability_attributes
        assert attributes["fan_modes"] == []
        assert attributes["min_temp"] is None
        assert attributes["max_temp"] is None


class TestCanalizationWithoutDeviceData:
    """The canalization device could not be read (yet)."""

    @pytest.fixture
    def entity(self, aguaiot_mock):
        device = build_device_without_values(
            aguaiot_mock, "test", CANALIZATION_REGISTER_MAP
        )
        return climate.AguaIOTCanalizationDevice(
            make_coordinator(), device, make_canalization_description(), MagicMock()
        )

    def test_fan_modes_is_empty(self, entity):
        assert entity.fan_modes == []

    def test_fan_mode_is_none(self, entity):
        assert entity.fan_mode is None

    def test_min_max_temp_are_unknown(self, entity):
        assert entity.min_temp is None
        assert entity.max_temp is None

    def test_capability_attributes_do_not_raise(self, entity):
        entity.hass = FakeHass()
        attributes = entity.capability_attributes
        assert attributes["fan_modes"] == []


class TestClimateWithDeviceData:
    """The device has been read successfully."""

    @pytest.fixture
    def entity(self, aguaiot_mock):
        device = build_device_from_fixture(aguaiot_mock, "test", REGISTER_MAP)
        return climate.AguaIOTAirDevice(make_coordinator(), device)

    def test_fan_modes(self, entity):
        assert entity.fan_modes == ["1", "2", "3"]

    def test_fan_mode(self, entity):
        assert entity.fan_mode == "2"

    def test_min_max_temp(self, entity):
        assert entity.min_temp == 15
        assert entity.max_temp == 30

    def test_temperatures(self, entity):
        assert entity.current_temperature == 20
        assert entity.target_temperature == 22


class TestClimateEntitiesCanBeAdded:
    """None of the climate entities may break while they are added."""

    def make_entities(self, aguaiot_mock):
        coordinator = make_coordinator()
        air = climate.AguaIOTAirDevice(
            coordinator,
            build_device_without_values(aguaiot_mock, "air", REGISTER_MAP),
        )
        water = climate.AguaIOTWaterDevice(
            coordinator,
            build_device_without_values(aguaiot_mock, "water", WATER_REGISTER_MAP),
            air,
        )
        canalization = climate.AguaIOTCanalizationDevice(
            coordinator,
            build_device_without_values(
                aguaiot_mock, "canalization", CANALIZATION_REGISTER_MAP
            ),
            make_canalization_description(),
            air,
        )
        return [air, water, canalization]

    def test_entities_without_device_data(self, aguaiot_mock):
        for entity in self.make_entities(aguaiot_mock):
            entity.hass = FakeHass()
            assert entity.capability_attributes is not None

    def test_entities_with_device_data(self, aguaiot_mock):
        coordinator = make_coordinator()
        device = build_device_from_fixture(aguaiot_mock, "air", REGISTER_MAP)
        water = build_device_from_fixture(aguaiot_mock, "water", WATER_REGISTER_MAP)
        canalization = build_device_from_fixture(
            aguaiot_mock, "canalization", CANALIZATION_REGISTER_MAP
        )
        entities = [
            climate.AguaIOTAirDevice(coordinator, device),
            climate.AguaIOTWaterDevice(coordinator, water, MagicMock()),
            climate.AguaIOTCanalizationDevice(
                coordinator, canalization, make_canalization_description(), MagicMock()
            ),
        ]

        for entity in entities:
            entity.hass = FakeHass()
            assert entity.capability_attributes is not None
