"""Test the alarm reset button."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.helpers import (
    build_device_from_fixture,
    build_device_without_values,
    load_component_module,
)

pytest.importorskip(
    "homeassistant.components.button", reason="homeassistant is required"
)

button = load_component_module("button")
const = load_component_module("const")


def make_register_map(status):
    """Return a register map with the alarm reset group sharing the status offset."""
    register = {
        "offset": 33,
        "mask": 255,
        "formula": "#",
        "formula_inverse": "#",
        "set_min": 0,
        "set_max": 13,
        "value_raw": str(status),
        "value": status,
    }
    return {
        "status_get": {**register, "reg_key": "status_get"},
        "allarm_reset_enable": {
            **register,
            "reg_key": "allarm_reset_enable",
            "reg_type": "ENABLE",
            "enable_val": [{"value": 12}, {"value": 13}],
        },
        "allarm_reset_set": {**register, "reg_key": "allarm_reset_set"},
    }


def make_button(device):
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.async_request_refresh = AsyncMock()
    return button.AguaIOTHeatingButton(coordinator, device, const.BUTTONS[0])


class TestAlarmResetButton:
    @pytest.mark.parametrize("status", [12, 13])
    def test_available_in_alarm(self, aguaiot_mock, status):
        device = build_device_from_fixture(
            aguaiot_mock, "test", make_register_map(status)
        )
        assert make_button(device).available is True

    @pytest.mark.parametrize("status", [0, 3, 7, 9])
    def test_unavailable_without_alarm(self, aguaiot_mock, status):
        device = build_device_from_fixture(
            aguaiot_mock, "test", make_register_map(status)
        )
        assert make_button(device).available is False

    def test_unavailable_without_device_data(self, aguaiot_mock):
        device = build_device_without_values(
            aguaiot_mock, "test", make_register_map(12)
        )
        assert make_button(device).available is False

    @pytest.mark.asyncio
    async def test_press_writes_zero(self, aguaiot_mock):
        device = build_device_from_fixture(aguaiot_mock, "test", make_register_map(12))
        device.set_register_value = AsyncMock()
        entity = make_button(device)

        await entity.async_press()

        device.set_register_value.assert_awaited_once_with("allarm_reset_set", 0)
        entity.coordinator.async_request_refresh.assert_awaited_once()
