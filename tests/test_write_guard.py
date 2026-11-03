"""EEPROM writes are counted before cloud or Bluetooth sends them."""

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.helpers import AguaIOTError, aguaiot, load_component_module

eeprom = load_component_module("eeprom")


def real_ble_class():
    """Load the Bluetooth transport without the host Bluetooth stack."""
    name = "aguaiot_component.local_ble"
    saved_module = sys.modules.get(name)
    stubs = {
        "bleak": ModuleType("bleak"),
        "bleak.exc": ModuleType("bleak.exc"),
        "bleak_retry_connector": ModuleType("bleak_retry_connector"),
        "homeassistant.components.bluetooth": ModuleType(
            "homeassistant.components.bluetooth"
        ),
    }
    stubs["bleak"].BleakClient = object
    stubs["bleak"].BleakError = Exception
    stubs["bleak.exc"].BleakGATTProtocolError = Exception
    stubs["bleak_retry_connector"].BleakClientWithServiceCache = object
    stubs["bleak_retry_connector"].establish_connection = None
    saved_stubs = {key: sys.modules.get(key) for key in stubs}
    sys.modules.pop(name, None)
    sys.modules.update(stubs)
    try:
        return load_component_module("local_ble").LocalBleAguaIOT
    finally:
        for key, module in saved_stubs.items():
            if module is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = module
        if saved_module is not None:
            sys.modules[name] = saved_module


def stove(offset):
    return SimpleNamespace(
        id_device="DEV_01",
        id_product=10,
        product_serial="AABBCCDDEEFF",
        get_register=lambda _key: {"offset": offset, "mask": 65535},
    )


def cloud(hass, device_options):
    client = aguaiot(
        "https://example.com",
        "123456",
        "a@b.c",
        "pw",
        "uuid",
        async_client=MagicMock(),
        hass=hass,
        device_options=device_options,
    )
    client.handle_webcall = AsyncMock(
        side_effect=[
            {"idRequest": "job-1"},
            {"jobAnswerStatus": "completed", "jobAnswerData": {"Cmd": "ok"}},
        ]
    )
    return client


@pytest.mark.asyncio
async def test_cloud_ram_write_still_posts():
    client = cloud(SimpleNamespace(data={}), {})
    await client._request_writing(stove(33), {"status_managed_set": 1})
    assert client.handle_webcall.await_args_list[0].args[0] == "POST"


@pytest.mark.asyncio
async def test_bluetooth_ram_write_still_opens_a_session():
    ble = real_ble_class()(
        SimpleNamespace(data={}),
        "https://example.com",
        "123456",
        "a@b.c",
        "pw",
        "uuid",
    )
    ble._run_authenticated_session = AsyncMock()
    await ble._request_writing(stove(33), {"status_managed_set": 1})
    ble._run_authenticated_session.assert_awaited_once()
    assert ble._run_authenticated_session.call_args.kwargs["retry"] is False


@pytest.mark.asyncio
async def test_cloud_write_error_keeps_the_count(eeprom_hass):
    client = cloud(eeprom_hass, {})
    client.handle_webcall = AsyncMock(side_effect=AguaIOTError("nope"))
    with pytest.raises(AguaIOTError, match="nope"):
        await client._request_writing(stove(32893), {"temp_air_set": 22})
    budget = eeprom_hass.data["aguaiot"]["eeprom_budgets"]["DEV_01"]
    assert len(budget.history) == 1
    client.handle_webcall = AsyncMock(
        side_effect=[
            {"idRequest": "job-1"},
            {"jobAnswerStatus": "completed", "jobAnswerData": {"Cmd": "ok"}},
        ]
    )
    await client._request_writing(stove(32893), {"temp_air_set": 22})
    assert len(budget.history) == 2


@pytest.mark.asyncio
async def test_cloud_status_failure_keeps_the_count(eeprom_hass, monkeypatch):
    module = load_component_module("aguaiot")
    monkeypatch.setattr(module.asyncio, "sleep", AsyncMock())

    def webcall(method, _url, _payload):
        if method == "POST":
            return {"idRequest": "job-1"}
        return False

    client = cloud(eeprom_hass, {})
    client.handle_webcall = AsyncMock(side_effect=webcall)
    with pytest.raises(AguaIOTError, match="Error while request device writing"):
        await client._request_writing(stove(32893), {"temp_air_set": 22})
    budget = eeprom_hass.data["aguaiot"]["eeprom_budgets"]["DEV_01"]
    assert len(budget.history) == 1
    assert client.handle_webcall.await_args_list[0].args[0] == "POST"


@pytest.mark.asyncio
async def test_cloud_ram_error_does_not_open_a_budget(eeprom_hass):
    client = cloud(eeprom_hass, {})
    client.handle_webcall = AsyncMock(side_effect=AguaIOTError("nope"))
    with pytest.raises(AguaIOTError, match="nope"):
        await client._request_writing(stove(33), {"status_managed_set": 1})
    assert eeprom_hass.data == {}


@pytest.mark.asyncio
async def test_bluetooth_write_error_keeps_the_count(eeprom_hass):
    ble = real_ble_class()(
        eeprom_hass,
        "https://example.com",
        "123456",
        "a@b.c",
        "pw",
        "uuid",
    )
    ble._run_authenticated_session = AsyncMock(side_effect=AguaIOTError("link down"))
    with pytest.raises(AguaIOTError, match="link down"):
        await ble._request_writing(stove(32893), {"temp_air_set": 22})
    budget = eeprom_hass.data["aguaiot"]["eeprom_budgets"]["DEV_01"]
    assert len(budget.history) == 1
    ble._run_authenticated_session = AsyncMock()
    await ble._request_writing(stove(32893), {"temp_air_set": 22})
    assert len(budget.history) == 2


@pytest.mark.asyncio
async def test_bluetooth_write_session_is_not_replayed_after_disconnect():
    from contextlib import asynccontextmanager

    ble = real_ble_class()(
        SimpleNamespace(data={}), "https://example.com", "123456", "a@b.c", "pw", "uuid"
    )

    @asynccontextmanager
    async def session(_device):
        yield SimpleNamespace(identity=AsyncMock())

    ble._device_session = session
    connection_error = load_component_module("aguaiot").AguaIOTConnectionError
    operation = AsyncMock(side_effect=connection_error("connection lost after write"))
    with pytest.raises(connection_error):
        await ble._run_authenticated_session(
            SimpleNamespace(name="Stove"), "writing", operation, retry=False
        )
    operation.assert_awaited_once()
