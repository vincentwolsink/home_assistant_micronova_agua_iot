"""Test the platforms with a device that could not be read (yet).

The register values of a device are unknown before it has been read
successfully. None of the entities may break because of that.
"""

from unittest.mock import MagicMock

import pytest

from tests.helpers import (
    build_device_from_fixture,
    build_device_without_values,
    load_component_module,
)

binary_sensor_component = pytest.importorskip(
    "homeassistant.components.binary_sensor", reason="homeassistant is required"
)
select_component = pytest.importorskip(
    "homeassistant.components.select", reason="homeassistant is required"
)
switch_component = pytest.importorskip(
    "homeassistant.components.switch", reason="homeassistant is required"
)
pytest.importorskip(
    "homeassistant.components.number", reason="homeassistant is required"
)

binary_sensor = load_component_module("binary_sensor")
number = load_component_module("number")
select = load_component_module("select")
sensor = load_component_module("sensor")
switch = load_component_module("switch")
const = load_component_module("const")

REGISTER_MAP = {
    "temp_air_get": {
        "reg_key": "temp_air_get",
        "offset": 1,
        "mask": 255,
        "formula": "#",
        "formula_inverse": "#",
        "value_raw": "20",
        "value": 20,
    },
    "standby_set": {
        "reg_key": "standby_set",
        "offset": 2,
        "mask": 255,
        "formula": "#",
        "formula_inverse": "#",
        "value_raw": "0",
        "value": 0,
    },
    "es_air_start_set": {
        "reg_key": "es_air_start_set",
        "offset": 3,
        "mask": 255,
        "formula": "#",
        "formula_inverse": "#",
        "set_min": 15,
        "set_max": 30,
        "step": 1,
        "value_raw": "20",
        "value": 20,
    },
}


def make_coordinator():
    """Return a coordinator mock of a successfully updated coordinator."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    return coordinator


def make_entities(aguaiot_mock, device):
    """Return an entity of every platform for the given device."""
    return [
        sensor.AguaIOTHeatingSensor(
            make_coordinator(),
            device,
            const.AguaIOTSensorEntityDescription(
                key="temp_air_get", name="Air temperature"
            ),
        ),
        binary_sensor.AguaIOTHeatingBinarySensor(
            make_coordinator(),
            device,
            binary_sensor_component.BinarySensorEntityDescription(
                key="standby_set", name="Standby"
            ),
        ),
        switch.AguaIOTHeatingSwitch(
            make_coordinator(),
            device,
            switch_component.SwitchEntityDescription(key="standby_set", name="Standby"),
        ),
        select.AguaIOTHeatingSelect(
            make_coordinator(),
            device,
            select_component.SelectEntityDescription(key="standby_set", name="Standby"),
        ),
        number.AguaIOTHeatingNumber(
            make_coordinator(),
            device,
            const.AguaIOTNumberEntityDescription(
                key="es_air_start_set",
                name="Energy Saving Start",
                native_step=1,
            ),
        ),
    ]


class TestPlatformsWithoutDeviceData:
    """The device could not be read (yet), so no register values are available."""

    @pytest.fixture
    def entities(self, aguaiot_mock):
        device = build_device_without_values(aguaiot_mock, "test", REGISTER_MAP)
        return make_entities(aguaiot_mock, device)

    def test_entities_have_no_value(self, entities):
        (
            sensor_entity,
            binary_sensor_entity,
            switch_entity,
            select_entity,
            number_entity,
        ) = entities
        assert sensor_entity.state is None
        assert binary_sensor_entity.state == "off"
        assert switch_entity.state == "off"
        assert select_entity.state is None
        assert number_entity.state is None

    def test_number_min_max_value_are_unknown(self, entities):
        number_entity = entities[-1]
        assert number_entity.native_min_value is None
        assert number_entity.native_max_value is None

    def test_number_capability_attributes_do_not_raise(self, entities):
        number_entity = entities[-1]
        attributes = number_entity.capability_attributes
        assert attributes["min"] is None
        assert attributes["max"] is None


class TestPlatformsWithDeviceData:
    """The device has been read successfully."""

    @pytest.fixture
    def entities(self, aguaiot_mock):
        device = build_device_from_fixture(aguaiot_mock, "test", REGISTER_MAP)
        return make_entities(aguaiot_mock, device)

    def test_number_min_max_value(self, entities):
        number_entity = entities[-1]
        assert number_entity.native_min_value == 15
        assert number_entity.native_max_value == 30


def test_eeprom_writes_sensor_is_diagnostic(aguaiot_mock):
    device = build_device_from_fixture(aguaiot_mock, "test", REGISTER_MAP)
    coordinator = make_coordinator()
    coordinator.eeprom_writes_per_day = {device.id_device: 4}
    entity = sensor.AguaIOTEepromWritesSensor(coordinator, device)

    assert entity.entity_category == const.EntityCategory.DIAGNOSTIC
    assert entity.native_value == 4
    assert entity.unique_id == f"{device.id_device}_eeprom_writes_per_day"
    assert entity.name == "EEPROM Writes (today)"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    [
        const.CONNECTION_MODE_CLOUD,
        const.CONNECTION_MODE_BLUETOOTH,
        const.CONNECTION_MODE_LOCAL_MQTT,
    ],
)
async def test_eeprom_writes_sensor_is_added_for_every_transport(aguaiot_mock, mode):
    device = build_device_from_fixture(aguaiot_mock, "test", REGISTER_MAP)
    coordinator = make_coordinator()
    coordinator.connection_mode = mode
    coordinator.agua.devices = [device]
    coordinator.eeprom_writes_per_day = {device.id_device: 2}
    config_entry = MagicMock(runtime_data=coordinator)
    add_entities = MagicMock()

    await sensor.async_setup_entry(MagicMock(), config_entry, add_entities)

    entities = add_entities.call_args.args[0]
    assert any(
        isinstance(entity, sensor.AguaIOTEepromWritesSensor) for entity in entities
    )
