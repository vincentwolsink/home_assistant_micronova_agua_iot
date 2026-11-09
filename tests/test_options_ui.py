"""MQTT options preserve existing account and stove settings."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.helpers import load_component_module

flow = load_component_module(
    "config_flow",
    stubbed_modules={
        "local_ble": {
            "DEFAULT_CHAR_UUID": "0000ffe1-0000-1000-8000-00805f9b34fb",
            "DEFAULT_SERVICE_UUID": "0000ffe5-0000-1000-8000-00805f9b34fb",
            "LocalBleAguaIOT": MagicMock,
        }
    },
)


def test_existing_options_get_configurable_eeprom_defaults(monkeypatch):
    options = flow.AguaIOTOptionsFlowHandler()
    entry = MagicMock(options={}, runtime_data=MagicMock())
    monkeypatch.setattr(type(options), "config_entry", property(lambda _self: entry))
    monkeypatch.setattr(options, "_languages", lambda: ["ENG"])
    validated = options._build_schema()(
        {
            "connection_mode": "connection_local_mqtt",
            "http_timeout": 20,
            "device_fixes": {},
        }
    )
    stored = validated
    assert stored["http_timeout"] == 20
    assert stored["failure_threshold"] == 3
    assert "allow_eeprom_writes" not in stored
    assert "max_eeprom_writes_per_hour" not in stored
    assert stored["max_eeprom_writes_per_day"] == 20


def test_failure_threshold_must_be_at_least_one(monkeypatch):
    options = flow.AguaIOTOptionsFlowHandler()
    entry = MagicMock(options={}, runtime_data=MagicMock())
    monkeypatch.setattr(type(options), "config_entry", property(lambda _self: entry))
    monkeypatch.setattr(options, "_languages", lambda: ["ENG"])
    schema = options._build_schema()

    assert schema({"device_fixes": {}})["failure_threshold"] == 3
    with pytest.raises(flow.vol.Invalid):
        schema({"device_fixes": {}, "failure_threshold": 0})


def test_options_work_before_runtime_setup(monkeypatch):
    from types import SimpleNamespace

    options = flow.AguaIOTOptionsFlowHandler()
    monkeypatch.setattr(
        type(options),
        "config_entry",
        property(lambda _self: SimpleNamespace(options={})),
    )
    assert options._languages() == ["ENG"]
    assert options._build_schema() is not None


@pytest.mark.asyncio
async def test_global_mqtt_settings_preserve_password_and_other_options(monkeypatch):
    options = flow.AguaIOTOptionsFlowHandler()
    entry = MagicMock(
        options={
            "connection_mode": "connection_local_mqtt",
            "language": "DEU",
            "mqtt_settings": {
                "hostname": "old.example",
                "port": 1883,
                "password": "test-only-secret",
            },
        },
    )
    monkeypatch.setattr(type(options), "config_entry", property(lambda _self: entry))
    client = MagicMock(
        connect=AsyncMock(), validate_local_connection=AsyncMock(), close=AsyncMock()
    )
    monkeypatch.setattr(options, "_build_client", lambda *_args: client)
    shown = await options.async_step_user({"connection_mode": "connection_local_mqtt"})
    assert shown["step_id"] == "mqtt_settings"
    assert "test-only-secret" not in str(shown)
    result = await options.async_step_mqtt_settings(
        {
            "hostname": "broker.example",
            "port": 1883,
            "username": "client",
        }
    )
    assert result["data"]["connection_mode"] == "connection_local_mqtt"
    assert result["data"]["language"] == "DEU"
    assert result["data"]["mqtt_settings"]["hostname"] == "broker.example"
    assert result["data"]["mqtt_settings"]["password"] == "test-only-secret"


@pytest.mark.asyncio
async def test_cloud_mode_does_not_open_mqtt_settings(monkeypatch):
    options = flow.AguaIOTOptionsFlowHandler()
    entry = MagicMock(options={"connection_mode": "connection_cloud"})
    monkeypatch.setattr(type(options), "config_entry", property(lambda _self: entry))
    client = MagicMock(connect=AsyncMock(), close=AsyncMock())
    monkeypatch.setattr(options, "_build_client", lambda *_args: client)
    result = await options.async_step_user({"connection_mode": "connection_cloud"})
    assert result["data"]["connection_mode"] == "connection_cloud"
    client.connect.assert_awaited_once()


def test_eeprom_limits_have_no_fixed_upper_ceiling(monkeypatch):
    options = flow.AguaIOTOptionsFlowHandler()
    entry = MagicMock(options={}, runtime_data=MagicMock())
    monkeypatch.setattr(type(options), "config_entry", property(lambda _self: entry))
    monkeypatch.setattr(options, "_languages", lambda: ["ENG"])
    schema = options._build_schema()
    data = {
        "max_eeprom_writes_per_day": 10000,
        "device_fixes": {},
    }
    validated = schema(data)
    assert validated["max_eeprom_writes_per_day"] == 10000
    assert "max_eeprom_writes_per_hour" not in validated
    with pytest.raises(flow.vol.Invalid):
        schema({**data, "max_eeprom_writes_per_day": 0})


@pytest.mark.asyncio
async def test_mqtt_setup_preserves_pending_options_and_validates_them(monkeypatch):
    options = flow.AguaIOTOptionsFlowHandler()
    entry = MagicMock(
        data={"ble_bootstrap_devices": [{"id_device": "one", "name": "Stove"}]},
        options={"connection_mode": "connection_cloud", "language": "ENG"},
    )
    monkeypatch.setattr(type(options), "config_entry", property(lambda _self: entry))
    client = MagicMock(
        connect=AsyncMock(), validate_local_connection=AsyncMock(), close=AsyncMock()
    )
    build = MagicMock(return_value=client)
    monkeypatch.setattr(options, "_build_client", build)
    shown = await options.async_step_user(
        {
            "connection_mode": "connection_local_mqtt",
            "language": "DEU",
            "max_eeprom_writes_per_day": 40,
        }
    )
    assert shown["step_id"] == "mqtt_settings"
    values = shown["data_schema"]({})
    assert "allow_eeprom_writes" not in values
    result = await options.async_step_mqtt_settings(values)
    assert result["data"]["connection_mode"] == "connection_local_mqtt"
    assert result["data"]["language"] == "DEU"
    assert "max_eeprom_writes_per_hour" not in result["data"]
    assert result["data"]["max_eeprom_writes_per_day"] == 40
    client.validate_local_connection.assert_awaited_once()
    client.close.assert_awaited_once()


def test_empty_runtime_languages_preserve_existing_language(monkeypatch):
    options = flow.AguaIOTOptionsFlowHandler()
    device = MagicMock()
    device.get_register_value_options_languages.return_value = []
    entry = MagicMock(options={"language": "DEU"})
    entry.runtime_data.agua.devices = [device]
    monkeypatch.setattr(type(options), "config_entry", property(lambda _self: entry))
    assert "DEU" in options._languages()
    validated = options._build_schema()({"device_fixes": {}, "language": "DEU"})
    assert validated["language"] == "DEU"
