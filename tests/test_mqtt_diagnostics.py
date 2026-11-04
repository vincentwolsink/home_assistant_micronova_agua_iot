"""Direct MQTT credentials must not be included in exported diagnostics."""

from unittest.mock import MagicMock

import pytest

from tests.helpers import load_component_module


@pytest.mark.asyncio
async def test_direct_mqtt_settings_are_redacted():
    diagnostics = load_component_module("diagnostics")
    entry = MagicMock()
    entry.runtime_data.agua.devices = []
    entry.as_dict.return_value = {
        "data": {
            "ble_bootstrap_devices": [
                {
                    "device_info": {
                        "reg_code": "private-registration-code",
                        "security_code": "private-cloud-code",
                    }
                }
            ]
        },
        "options": {
            "mqtt_settings": {
                "hostname": "broker.example",
                "username": "private-user",
                "password": "private-test-secret",
            }
        },
    }
    result = await diagnostics.async_get_config_entry_diagnostics(MagicMock(), entry)
    assert "private-test-secret" not in str(result)
    assert "private-user" not in str(result)
    assert "private-registration-code" not in str(result)
    assert "private-cloud-code" not in str(result)
