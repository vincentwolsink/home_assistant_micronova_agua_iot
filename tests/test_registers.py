"""Test the resolution of vendor specific register naming variants."""

from dataclasses import dataclass

import pytest

from tests.helpers import build_device_from_fixture, load_component_module

registers = load_component_module("registers")


def make_register(key, offset, value=1, reg_type="GET", enable_val=None):
    register = {
        "reg_key": key,
        "reg_type": reg_type,
        "offset": offset,
        "mask": 255,
        "formula": "#",
        "formula_inverse": "#",
        "set_min": 0,
        "set_max": 255,
        "is_hex": False,
        "value_raw": str(value),
        "value": value,
    }
    if enable_val is not None:
        register["enable_val"] = [{"value": v} for v in enable_val]
    return register


def make_device(aguaiot_mock, values):
    """Build a device from {key: value}; *_enable keys become ENABLE registers."""
    register_map = {
        key: make_register(
            key,
            offset,
            value,
            reg_type="ENABLE" if key.endswith("_enable") else "GET",
        )
        for offset, (key, value) in enumerate(values.items(), start=1)
    }
    return build_device_from_fixture(aguaiot_mock, "test", register_map)


@pytest.mark.parametrize(
    ("key", "canonical"),
    [
        # Variant digit after a word
        ("temp_air2_get", "temp_air_get"),
        ("temp_air3_get", "temp_air_get"),
        ("vent_front2_set", "vent_front_set"),
        ("temp_h2o_boiler2_get", "temp_h2o_boiler_get"),
        # Variant digit before a word
        ("canalization_2dx_get", "canalization_dx_get"),
        ("canalization_2dx_temp_air_get", "canalization_dx_temp_air_get"),
        # Numbered units are not variants
        ("canalization_1_set", "canalization_1_set"),
        ("canalization_1_2_vent_set", "canalization_1_2_vent_set"),
        ("thermostat_contact_2_get", "thermostat_contact_2_get"),
        ("multifire_1_1_set", "multifire_1_1_set"),
        # Digits that are part of a word
        ("temp_h2o_get", "temp_h2o_get"),
        ("p_quality_p12_get", "p_quality_p12_get"),
        # The first segment names the function: fan2 is a second fan
        ("fan2_mode_set", "fan2_mode_set"),
        # Case insensitive
        ("Temp_Air2_GET", "temp_air_get"),
    ],
)
def test_canonical_key(key, canonical):
    assert registers.canonical_key(key) == canonical


def test_aliases_prefer_exact_then_variant_free():
    aliases = registers.RegisterAliases(
        ["temp_air3_get", "temp_air2_get", "temp_air_get", "temp_air_set"]
    )
    assert aliases.aliases("temp_air_get") == [
        "temp_air_get",
        "temp_air2_get",
        "temp_air3_get",
    ]
    assert aliases.aliases("temp_air3_get") == [
        "temp_air3_get",
        "temp_air_get",
        "temp_air2_get",
    ]
    assert aliases.aliases("temp_air_set") == ["temp_air_set"]
    assert aliases.aliases("temp_water_get") == []


@pytest.mark.parametrize(
    ("existing", "lookup", "expected"),
    [
        # set without, get with variant digit
        (["temp_air_set", "temp_air2_get"], "temp_air_get", "temp_air2_get"),
        # set with, get without variant digit
        (["vent_front2_set", "vent_front_get"], "vent_front2_get", "vent_front_get"),
        # digit in front of the word
        (
            ["canalization_dx_set", "canalization_2dx_get"],
            "canalization_dx_get",
            "canalization_2dx_get",
        ),
        # a variant not seen in the fixtures yet
        (["vent_rear3_set", "vent_rear_get"], "vent_rear_set", "vent_rear3_set"),
        # numbered units are never aliases of each other
        (["canalization_2_set"], "canalization_1_set", None),
    ],
)
def test_find(existing, lookup, expected):
    assert registers.RegisterAliases(existing).find(lookup) == expected


def test_device_find_register_conditions(aguaiot_mock):
    device = make_device(
        aguaiot_mock,
        {
            "temp_air_get": 0,
            "temp_air2_enable": 0,
            "temp_air2_get": 21,
            "temp_air3_get": 22,
        },
    )
    assert device.find_register("temp_air_get") == "temp_air_get"
    # temp_air_get has no value, temp_air2_get is disabled
    assert device.find_register("temp_air_get", enabled=True, has_value=True) == (
        "temp_air3_get"
    )


def test_device_enable_register_variant(aguaiot_mock):
    """The enable register may use another variant than the register."""
    device = make_device(aguaiot_mock, {"vent_front2_set": 3, "vent_front_enable": 0})
    assert not device.get_register_enabled("vent_front2_set")


@dataclass
class Description:
    key: str
    force_enabled: bool = False


def test_bind_descriptions(aguaiot_mock):
    device = make_device(
        aguaiot_mock,
        {
            "temp_air2_get": 20,
            "temp_air3_get": 21,
            "vent_front_get": 2,
            "vent_rear_enable": 0,
            "vent_rear_get": 1,
        },
    )
    bound = registers.bind_descriptions(
        device,
        [
            Description("temp_air_get"),
            Description("temp_air2_get"),
            Description("temp_air3_get"),
            Description("vent_front2_get"),
            Description("vent_rear2_get"),
        ],
    )
    # temp_air_get has no register of its own: its variants are taken by the
    # descriptions naming them directly. vent_rear is disabled.
    assert [d.key for d in bound] == [
        "temp_air2_get",
        "temp_air3_get",
        "vent_front_get",
    ]

    bound = registers.bind_descriptions(device, [Description("vent_rear2_get", True)])
    assert [d.key for d in bound] == ["vent_rear_get"]
