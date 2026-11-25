"""Test the stove clock synchronization device command."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from tests.helpers import build_device_from_fixture, load_component_module

const = load_component_module("const")


REGISTER_MAP = {
    key: {
        "offset": offset,
        "mask": 255,
        "formula": "#",
        "formula_inverse": "#",
        "set_min": 0,
        "set_max": 255,
        "value_raw": "1",
        "value": 1,
        "reg_key": key,
    }
    for offset, key in enumerate(const.CLOCK_REGISTERS, start=1)
}


@pytest.mark.asyncio
async def test_sync_clock_writes_time_and_date(aguaiot_mock):
    device = build_device_from_fixture(aguaiot_mock, "test", REGISTER_MAP)
    device.set_register_values = AsyncMock()

    await device.sync_clock(datetime(2026, 11, 14, 13, 45, tzinfo=UTC))

    device.set_register_values.assert_awaited_once_with(
        {
            "clock_hour_set": 13,
            "clock_minute_set": 45,
            "calendar_day_set": 14,
            "calendar_month_set": 11,
            "calendar_year_set": 2026,
        },
        limit_value_raw=True,
    )
