"""Test the update coordinator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.helpers import load_component_module

try:
    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
    from homeassistant.exceptions import ConfigEntryNotReady
    from homeassistant.helpers.update_coordinator import UpdateFailed
except ImportError:  # pragma: no cover
    pytest.skip("homeassistant is required", allow_module_level=True)


class StubLocalBleAguaIOT:
    """Placeholder for the Bluetooth transport, which is not tested here."""


coordinator_module = load_component_module(
    "coordinator",
    stubbed_modules={
        "local_ble": {
            "DEFAULT_CHAR_UUID": "0000ffe1-0000-1000-8000-00805f9b34fb",
            "DEFAULT_SERVICE_UUID": "0000ffe5-0000-1000-8000-00805f9b34fb",
            "LocalBleAguaIOT": StubLocalBleAguaIOT,
        }
    },
)
const = load_component_module("const")

AguaIOTDataUpdateCoordinator = coordinator_module.AguaIOTDataUpdateCoordinator
AguaIOTUpdateError = coordinator_module.AguaIOTUpdateError


def make_config_entry():
    """Return a config entry stub."""
    config_entry = MagicMock()
    config_entry.state = ConfigEntryState.SETUP_IN_PROGRESS
    config_entry.data = {
        const.CONF_API_URL: "https://example.com",
        const.CONF_CUSTOMER_CODE: "000000",
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test",
        const.CONF_UUID: "test-uuid",
    }
    config_entry.options = {}
    return config_entry


def make_coordinator():
    """Return a coordinator with a mocked AguaIOT transport."""
    coordinator = AguaIOTDataUpdateCoordinator(
        hass=MagicMock(), config_entry=make_config_entry()
    )
    coordinator.agua = MagicMock()
    coordinator.agua.connect = AsyncMock()
    coordinator.agua.update = AsyncMock()
    return coordinator


class TestUpdate:
    @pytest.mark.asyncio
    async def test_update_error_raises_update_failed(self):
        coordinator = make_coordinator()
        coordinator.agua.update = AsyncMock(
            side_effect=AguaIOTUpdateError("terminated")
        )

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_successful_update_does_not_raise(self):
        coordinator = make_coordinator()

        assert await coordinator._async_update_data() is None
        assert coordinator.last_update_success is True


class TestFirstRefresh:
    @pytest.mark.asyncio
    async def test_update_error_raises_config_entry_not_ready(self):
        coordinator = make_coordinator()
        coordinator.agua.update = AsyncMock(
            side_effect=AguaIOTUpdateError("terminated")
        )

        with pytest.raises(ConfigEntryNotReady):
            await coordinator.async_config_entry_first_refresh()

        assert coordinator.last_update_success is False

    @pytest.mark.asyncio
    async def test_setup_error_raises_config_entry_not_ready(self):
        coordinator = make_coordinator()
        coordinator.agua.connect = AsyncMock(
            side_effect=AguaIOTUpdateError("terminated")
        )

        with pytest.raises(ConfigEntryNotReady):
            await coordinator.async_config_entry_first_refresh()

        assert coordinator.last_update_success is False

    @pytest.mark.asyncio
    async def test_setup_succeeds_after_a_failed_read(self):
        coordinator = make_coordinator()
        coordinator.agua.update = AsyncMock(
            side_effect=AguaIOTUpdateError("terminated")
        )

        with pytest.raises(ConfigEntryNotReady):
            await coordinator.async_config_entry_first_refresh()

        # The next attempt of Home Assistant to set up the config entry
        # succeeds as soon as the device can be read again.
        coordinator.agua.update = AsyncMock(return_value=None)
        await coordinator.async_config_entry_first_refresh()

        assert coordinator.last_update_success is True
