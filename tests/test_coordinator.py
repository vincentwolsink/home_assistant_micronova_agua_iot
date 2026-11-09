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

    def __init__(self, *args, **kwargs):
        pass


coordinator_module = load_component_module(
    "coordinator",
    stubbed_modules={
        "local_ble": {
            "DEFAULT_CHAR_UUID": "0000ffe1-0000-1000-8000-00805f9b34fb",
            "DEFAULT_SERVICE_UUID": "0000ffe5-0000-1000-8000-00805f9b34fb",
            "LocalBleAguaIOT": StubLocalBleAguaIOT,
        },
    },
)
const = load_component_module("const")
LocalMqttAguaIOT = load_component_module("local_mqtt").LocalMqttAguaIOT

AguaIOTDataUpdateCoordinator = coordinator_module.AguaIOTDataUpdateCoordinator
AguaIOTUpdateError = coordinator_module.AguaIOTUpdateError


def make_config_entry(connection_mode=None):
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
    options = {}
    if connection_mode:
        options[const.CONF_CONNECTION_MODE] = connection_mode
    config_entry.options = options
    return config_entry


def make_coordinator(connection_mode=None):
    """Return a coordinator with a mocked AguaIOT transport."""
    coordinator = AguaIOTDataUpdateCoordinator(
        hass=MagicMock(), config_entry=make_config_entry(connection_mode)
    )
    if not connection_mode or connection_mode == const.CONNECTION_MODE_CLOUD:
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

    @pytest.mark.asyncio
    async def test_update_collects_eeprom_usage_for_every_transport(self, monkeypatch):
        coordinator = make_coordinator()
        coordinator.agua.update = AsyncMock()
        coordinator.agua.devices = [
            MagicMock(id_device="DEV_01", wifi_mac="AABBCCDDEEFF")
        ]
        coordinator._async_persist_ble_bootstrap_if_needed = AsyncMock()
        usage = AsyncMock(return_value=7)
        monkeypatch.setattr(coordinator_module, "eeprom_daily_writes_for_device", usage)

        await coordinator._async_update_data()

        assert coordinator.eeprom_writes_per_day == {"DEV_01": 7}
        usage.assert_awaited_once()


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


def make_transport_mock():
    """Return a transport stub that can be refreshed by the coordinator."""
    agua = MagicMock()
    agua.devices = []
    agua.cache_dirty = False
    agua.connect = AsyncMock()
    agua.update = AsyncMock()
    return agua


class TestFailureThreshold:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "mode",
        [
            const.CONNECTION_MODE_CLOUD,
            const.CONNECTION_MODE_BLUETOOTH,
            const.CONNECTION_MODE_LOCAL_MQTT,
        ],
    )
    async def test_transient_failures_keep_entities_available(self, mode):
        coordinator = make_coordinator(mode)
        coordinator.agua = make_transport_mock()
        await coordinator.async_config_entry_first_refresh()
        assert coordinator.last_update_success is True

        coordinator.agua.update.side_effect = AguaIOTUpdateError("terminated")
        for _ in range(const.DEFAULT_FAILURE_THRESHOLD - 1):
            await coordinator.async_refresh()
            assert coordinator.last_update_success is True

        await coordinator.async_refresh()
        assert coordinator.last_update_success is False

    @pytest.mark.asyncio
    async def test_success_resets_the_failure_counter(self):
        coordinator = make_coordinator()
        coordinator.agua = make_transport_mock()
        await coordinator.async_config_entry_first_refresh()

        coordinator.agua.update.side_effect = AguaIOTUpdateError("terminated")
        await coordinator.async_refresh()
        await coordinator.async_refresh()
        assert coordinator.last_update_success is True

        coordinator.agua.update.side_effect = None
        await coordinator.async_refresh()
        assert coordinator.last_update_success is True

        coordinator.agua.update.side_effect = AguaIOTUpdateError("terminated")
        await coordinator.async_refresh()
        await coordinator.async_refresh()
        assert coordinator.last_update_success is True

        await coordinator.async_refresh()
        assert coordinator.last_update_success is False

    @pytest.mark.asyncio
    async def test_configured_failure_threshold_is_used(self):
        entry = make_config_entry()
        entry.options[const.CONF_FAILURE_THRESHOLD] = 1
        coordinator = AguaIOTDataUpdateCoordinator(hass=MagicMock(), config_entry=entry)
        coordinator.agua = make_transport_mock()
        await coordinator.async_config_entry_first_refresh()

        coordinator.agua.update.side_effect = AguaIOTUpdateError("terminated")
        await coordinator.async_refresh()

        assert coordinator.last_update_success is False


class TestConnectionModes:
    def test_local_mqtt_mode_initialization(self):
        coordinator = make_coordinator(const.CONNECTION_MODE_LOCAL_MQTT)
        assert isinstance(coordinator.agua, LocalMqttAguaIOT)
        assert coordinator.connection_mode == const.CONNECTION_MODE_LOCAL_MQTT

    def test_local_mqtt_receives_global_settings(self):
        entry = make_config_entry(const.CONNECTION_MODE_LOCAL_MQTT)
        entry.options[const.CONF_MQTT_SETTINGS] = {
            "hostname": "broker.example",
            "port": 1883,
        }
        coordinator = AguaIOTDataUpdateCoordinator(hass=MagicMock(), config_entry=entry)
        assert (
            coordinator.agua._mqtt_settings == entry.options[const.CONF_MQTT_SETTINGS]
        )


class TestCloudBootstrapForLocalConnections:
    @pytest.mark.asyncio
    async def test_cloud_refresh_caches_available_register_maps(self):
        coordinator = make_coordinator()
        cached = {
            "product_serial": "AABBCCDDEEFF",
            "register_map": {"temp_air_get": {"offset": 1}},
        }
        coordinator.agua.devices = [
            MagicMock(export_cache=MagicMock(return_value=cached))
        ]
        await coordinator._async_persist_ble_bootstrap_if_needed()
        update = coordinator.hass.config_entries.async_update_entry
        assert update.call_args.kwargs["data"][const.CONF_BLE_BOOTSTRAP_DEVICES] == [
            cached
        ]

    @pytest.mark.asyncio
    async def test_cloud_refresh_does_not_save_incomplete_maps(self):
        coordinator = make_coordinator()
        coordinator.agua.devices = [
            MagicMock(export_cache=MagicMock(return_value={"register_map": {}}))
        ]
        await coordinator._async_persist_ble_bootstrap_if_needed()
        coordinator.hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_cloud_polling_does_not_rewrite_bootstrap_on_every_value_change():
    coordinator = make_coordinator()
    cached = {"register_map": {"temp_air_get": {"offset": 1, "value_raw": "20"}}}
    coordinator.agua.devices = [MagicMock(export_cache=MagicMock(return_value=cached))]
    await coordinator._async_persist_ble_bootstrap_if_needed()
    cached["register_map"]["temp_air_get"]["value_raw"] = "21"
    await coordinator._async_persist_ble_bootstrap_if_needed()
    coordinator.hass.config_entries.async_update_entry.assert_called_once()


@pytest.mark.parametrize(
    "mode",
    [
        const.CONNECTION_MODE_CLOUD,
        const.CONNECTION_MODE_BLUETOOTH,
        const.CONNECTION_MODE_LOCAL_MQTT,
    ],
)
def test_configured_eeprom_limits_reach_every_transport(monkeypatch, mode):
    entry = make_config_entry(mode)
    entry.options.update(max_eeprom_writes_per_day=250)
    ble = MagicMock()
    monkeypatch.setattr(coordinator_module, "LocalBleAguaIOT", ble)
    coordinator = AguaIOTDataUpdateCoordinator(hass=MagicMock(), config_entry=entry)
    expected = {"max_eeprom_writes_per_day": 250}
    if mode == const.CONNECTION_MODE_BLUETOOTH:
        assert ble.call_args.kwargs["eeprom_limits"] == expected
    else:
        assert coordinator.agua.eeprom_limits == expected
