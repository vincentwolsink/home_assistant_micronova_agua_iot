"""Unit tests for the LocalMqttAguaIOT transport."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.helpers import load_component_module

local_mqtt_module = load_component_module("local_mqtt")
LocalMqttAguaIOT = local_mqtt_module.LocalMqttAguaIOT


def make_dummy_cached_devices():
    return [
        {
            "id": 1,
            "id_device": "DEV_01",
            "id_product": 10,
            "product_serial": "SERIAL-123456",
            "mac": "A1B2C3D4E5F6",
            "name": "Living Room Stove",
            "is_online": True,
            "name_product": "Pellet Stove",
            "id_registers_map": 5,
            "device_info": {"reg_code": "98765432"},
            "register_map": {
                "temp_air_get": {
                    "offset": 1,
                    "mask": 65535,
                    "formula": "# / 10",
                    "reg_type": "GET",
                },
                "temp_smoke_get": {
                    "offset": 6,
                    "mask": 65535,
                    "formula": "#",
                    "reg_type": "GET",
                },
                "status_managed_set": {
                    "offset": 33,
                    "mask": 65535,
                    "formula": "#",
                    "reg_type": "SET",
                },
                "temp_air_set": {
                    "offset": 32893,
                    "mask": 65535,
                    "formula": "#",
                    "reg_type": "SET",
                    "value_raw": "22",
                },
                "chrono_p1_start_set": {
                    "offset": 32826,
                    "mask": 65535,
                    "formula": "#",
                    "reg_type": "SET",
                },
            },
        }
    ]


def make_test_instance(
    cached_devices=None,
):
    """Create a LocalMqttAguaIOT test instance with dummy credentials."""
    hass = MagicMock()
    return LocalMqttAguaIOT(
        hass=hass,
        api_url="https://example.com",
        customer_code="123456",
        email="test@example.com",
        password="secret_password",
        unique_id="uuid-test-1234",
        cached_devices=cached_devices,
    )


class TestLocalMqttBasics:
    """Test instance creation, cache helpers, and identifier sanitization."""

    def test_clean_identifier(self):
        client = make_test_instance()
        assert client._clean_identifier("AA:BB:CC:11:22:33") == "AABBCC112233"
        assert client._clean_identifier("aa-bb-cc-dd-ee-ff") == "AABBCCDDEEFF"
        assert client._clean_identifier(None) is None
        assert client._clean_identifier("") is None

    def test_init_defaults(self):
        client = make_test_instance()
        assert client._unsubscribe is None
        assert client.devices == []
        assert client.cache_dirty is False

    def test_load_cached_devices(self):
        cached = make_dummy_cached_devices()
        client = make_test_instance(cached_devices=cached)
        client._load_cached_devices(cached)

        assert len(client.devices) == 1
        assert client._device_mac == "A1B2C3D4E5F6"
        assert client._security_code == "98765432"
        # Seeded from value_raw in register_map
        assert client._register_values[32893] == 22

    def test_collect_readable_offsets_includes_setpoints_excludes_chrono(self):
        cached = make_dummy_cached_devices()
        client = make_test_instance(cached_devices=cached)
        client._load_cached_devices(cached)

        offsets = client._collect_readable_offsets(client.devices[0])
        assert 1 in offsets
        assert 6 in offsets
        assert 33 in offsets
        assert 32893 in offsets
        assert 32826 not in offsets


@pytest.fixture
def mqtt_api(monkeypatch):
    """Provide the public HA MQTT API without running a live broker."""
    unsubscribes = [MagicMock(), MagicMock()]
    api = SimpleNamespace(
        async_wait_for_mqtt_client=AsyncMock(return_value=True),
        async_subscribe=AsyncMock(side_effect=unsubscribes),
        async_publish=AsyncMock(),
        async_subscribe_connection_status=MagicMock(return_value=MagicMock()),
        is_connected=MagicMock(return_value=True),
        unsubscribes=unsubscribes,
    )
    monkeypatch.setattr(
        local_mqtt_module, "async_import_module", AsyncMock(return_value=api)
    )
    monkeypatch.setitem(sys.modules, "homeassistant.components.mqtt", api)
    # Python's from-import can also resolve a cached package attribute.
    import homeassistant.components

    monkeypatch.setattr(homeassistant.components, "mqtt", api, raising=False)
    return api


def message(payload, *, retain=False):
    return SimpleNamespace(payload=json.dumps(payload), retain=retain)


class TestLocalMqttProtocolFlow:
    """Exercise the Navel protocol through Home Assistant's shared MQTT client."""

    @pytest.mark.asyncio
    async def test_connect_subscribes_and_authenticates_existing_stove(self, mqtt_api):
        client = make_test_instance(cached_devices=make_dummy_cached_devices())
        await client.connect()
        assert [call.args[1] for call in mqtt_api.async_subscribe.call_args_list] == [
            "navel/A1B2C3D4E5F6",
            "master/responses/navel/A1B2C3D4E5F6",
        ]
        publish = mqtt_api.async_publish.call_args
        assert json.loads(publish.args[2])["pl"]["Cmd"] == "Identity"
        assert publish.kwargs == {"qos": 0, "retain": False}
        await client._message_received(
            message({"mt": "R", "pl": {"Cmd": "Identity", "Result": 0}})
        )

        async def live_reply(_hass, _topic, payload, **_kwargs):
            query = json.loads(payload)
            if query["pl"]["Cmd"] == "RequestReading":
                await client._message_received(
                    message(
                        {
                            "mt": "R",
                            "pl": {
                                "Cmd": "RequestReading",
                                "Items": [1],
                                "Values": [225],
                            },
                        }
                    )
                )

        mqtt_api.async_publish.side_effect = live_reply
        assert await client.validate_local_connection() == {
            "device_mac": "A1B2C3D4E5F6"
        }
        await client.close()
        await client.close()
        for unsubscribe in mqtt_api.unsubscribes:
            unsubscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_mqtt_is_actionable(self, mqtt_api):
        mqtt_api.async_wait_for_mqtt_client.return_value = False
        client = make_test_instance(cached_devices=make_dummy_cached_devices())
        with pytest.raises(
            local_mqtt_module.AguaIOTConnectionError,
            match="Configure Home Assistant MQTT",
        ):
            await client.connect()
        mqtt_api.async_subscribe.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_subscription_failure_cleans_up(self, mqtt_api):
        mqtt_api.async_subscribe.side_effect = [
            mqtt_api.unsubscribes[0],
            RuntimeError("subscribe failed"),
        ]
        client = make_test_instance(cached_devices=make_dummy_cached_devices())
        with pytest.raises(
            local_mqtt_module.AguaIOTConnectionError, match="Could not initialize"
        ):
            await client.connect()
        mqtt_api.unsubscribes[0].assert_called_once()
        assert client._unsubscribe is None

    @pytest.mark.asyncio
    async def test_stove_handshake_ping_and_reading(self, mqtt_api):
        client = make_test_instance(cached_devices=make_dummy_cached_devices())
        await client.connect()
        mqtt_api.async_publish.reset_mock()
        await client._message_received(
            message(
                {
                    "mi": "identity-1",
                    "mt": "C",
                    "pl": {
                        "Cmd": "Identity",
                        "Id": "A1B2C3D4E5F6",
                        "Security": "87654321",
                    },
                }
            )
        )
        payloads = [
            json.loads(call.args[2]) for call in mqtt_api.async_publish.call_args_list
        ]
        assert payloads[0]["mt"] == "A"
        assert payloads[0]["mi"] == "identity-1"
        assert payloads[1]["pl"]["Security"] == "87654321"
        assert client.cache_dirty
        cache = client.export_bootstrap_cache()
        restored = make_test_instance(cached_devices=cache)
        restored._load_cached_devices(cache)
        assert restored._security_code == "87654321"
        await client._message_received(
            message({"mi": "ping-1", "mt": "C", "pl": {"Cmd": "Ping"}})
        )
        assert json.loads(mqtt_api.async_publish.call_args.args[2])["mi"] == "ping-1"
        await client._message_received(
            message(
                {
                    "mt": "R",
                    "pl": {
                        "Cmd": "RequestReading",
                        "Items": [1, 6, 32893],
                        "Values": [225, 115, 23],
                    },
                }
            )
        )
        assert client._register_values[1] == 225
        assert client._register_values[32893] == 23
        assert client._response_event.is_set()
        client._identity_ready.clear()
        client._identity_pending = False
        mqtt_api.async_publish.reset_mock()
        published = []

        async def answer_after_identity(_hass, _topic, payload, **_kwargs):
            query = json.loads(payload)
            published.append(query["pl"]["Cmd"])
            if query["pl"]["Cmd"] == "Identity":
                await client._message_received(
                    message({"mt": "R", "pl": {"Cmd": "Identity", "Result": 0}})
                )
            elif query["pl"]["Cmd"] == "RequestReading":
                assert client._identity_ready.is_set()
                await client._message_received(
                    message(
                        {
                            "mt": "R",
                            "pl": {
                                "Cmd": "RequestReading",
                                "Items": [1],
                                "Values": [226],
                            },
                        }
                    )
                )

        mqtt_api.async_publish.side_effect = answer_after_identity
        assert (await client._fetch_device_information(client.devices[0]))[1] == 226
        assert published == ["Identity", "RequestReading"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "payload,retained",
        [
            ({"mt": "Q", "pl": {"Cmd": "Identity"}}, False),
            ({"mt": "A", "pl": {"Cmd": "Ping"}}, False),
            ({"mt": "C", "pl": {"Cmd": "Ping"}}, True),
            ({"mt": "C", "pl": {"Cmd": "Identity", "Id": "FFFFFFFFFFFF"}}, False),
            (
                {
                    "mt": "R",
                    "pl": {
                        "Cmd": "RequestReading",
                        "Items": [1],
                        "Values": ["invalid"],
                    },
                },
                False,
            ),
            (
                {
                    "mt": "R",
                    "pl": {"Cmd": "RequestReading", "Items": [1, 6], "Values": [225]},
                },
                False,
            ),
            ({"mt": "C", "pl": {"Cmd": "Identity", "Id": 123}}, False),
            (
                {"mt": "R", "pl": {"Cmd": "RequestReading", "Items": [], "Values": []}},
                False,
            ),
            (
                {
                    "mt": "R",
                    "pl": {
                        "Cmd": "RequestReading",
                        "Items": [1],
                        "Values": [float("inf")],
                    },
                },
                False,
            ),
            ([], False),
        ],
    )
    async def test_ignores_echo_retained_foreign_and_invalid_messages(
        self, mqtt_api, payload, retained
    ):
        client = make_test_instance(cached_devices=make_dummy_cached_devices())
        await client.connect()
        mqtt_api.async_publish.reset_mock()
        await client._message_received(message(payload, retain=retained))
        mqtt_api.async_publish.assert_not_called()
        assert not client._response_event.is_set()

    @pytest.mark.asyncio
    async def test_disconnected_broker_rejects_publish(self, mqtt_api):
        client = make_test_instance(cached_devices=make_dummy_cached_devices())
        await client.connect()
        mqtt_api.is_connected.return_value = False
        with pytest.raises(
            local_mqtt_module.AguaIOTConnectionError, match="not connected"
        ):
            await client._send_mqtt_publish("navel/A1B2C3D4E5F6", {"mt": "Q"})


@pytest.mark.asyncio
async def test_cached_values_do_not_pass_live_connection_check(mqtt_api):
    client = make_test_instance(cached_devices=make_dummy_cached_devices())
    await client.connect()
    client.buffer_read_timeout = 0.01
    assert client._register_values  # Cache exists, but no live stove has answered.
    with pytest.raises(local_mqtt_module.LocalMqttSetupError, match="No live reading"):
        await client.validate_local_connection()
    await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("connected", [True, False])
async def test_poll_never_reports_cached_readings_as_live(mqtt_api, connected):
    client = make_test_instance(cached_devices=make_dummy_cached_devices())
    await client.connect()
    client.buffer_read_timeout = 0.01
    assert client._register_values
    if not connected:
        await client.close()
    try:
        with pytest.raises(local_mqtt_module.AguaIOTConnectionError):
            await client._fetch_device_information(client.devices[0])
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_cloud_mac_uses_shared_ha_mqtt_without_other_integration(mqtt_api):
    cached = make_dummy_cached_devices()
    cached[0]["mac"] = "AA:BB:CC:DD:EE:FF"
    cached[0]["id_device"] = "cloud-id"
    client = make_test_instance(cached_devices=cached)
    client.hass.data = {}
    try:
        await client.connect()
        assert client._device_mac == "AABBCCDDEEFF"
        assert not client._owns_mqtt
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_missing_cloud_mac_is_actionable(mqtt_api):
    cached = make_dummy_cached_devices()
    cached[0].pop("mac")
    client = make_test_instance(cached_devices=cached)
    with pytest.raises(local_mqtt_module.LocalMqttSetupError) as err:
        await client.connect()
    assert err.value.key == "invalid_mac"
    mqtt_api.async_subscribe.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("offset", [32767, 32768])
async def test_only_high_offsets_use_the_eeprom_budget(mqtt_api, offset):
    client = make_test_instance(cached_devices=make_dummy_cached_devices())
    client.hass.data = {
        "aguaiot": {"eeprom_budgets": {"DEV_01": MagicMock(reserve=AsyncMock())}}
    }
    await client.connect()
    client._identity_ready.set()
    mqtt_api.async_publish.reset_mock()
    client._fetch_device_information = AsyncMock(return_value={})
    try:
        await client._request_writing(
            client.devices[0],
            {"Cmd": "RequestWriting", "Items": [offset], "Values": [1]},
        )
        mqtt_api.async_publish.assert_awaited_once()
        budget = client.hass.data["aguaiot"]["eeprom_budgets"]["DEV_01"]
        if offset >= 32768:
            budget.reserve.assert_awaited_once()
        else:
            budget.reserve.assert_not_awaited()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_failed_mqtt_publish_keeps_the_eeprom_count(mqtt_api, eeprom_hass):
    eeprom = load_component_module("eeprom")

    budget = eeprom.EepromBudget(eeprom_hass, "DEV_01")
    client = make_test_instance(cached_devices=make_dummy_cached_devices())
    await client.connect()
    client._identity_ready.set()
    client.hass.data = {"aguaiot": {"eeprom_budgets": {"DEV_01": budget}}}
    mqtt_api.async_publish.reset_mock(side_effect=True)
    mqtt_api.async_publish.side_effect = local_mqtt_module.HomeAssistantError("down")
    try:
        with pytest.raises(local_mqtt_module.AguaIOTConnectionError, match="publish"):
            await client._request_writing(
                client.devices[0],
                {"Cmd": "RequestWriting", "Items": [32893], "Values": [23]},
            )
        assert len(budget.history) == 1
        mqtt_api.async_publish.side_effect = local_mqtt_module.HomeAssistantError(
            "Delivery is uncertain. The command was not retried."
        )
        with pytest.raises(local_mqtt_module.AguaIOTConnectionError, match="uncertain"):
            await client._request_writing(
                client.devices[0],
                {"Cmd": "RequestWriting", "Items": [32893], "Values": [23]},
            )
        assert len(budget.history) == 2
        with open(budget.store.path) as saved:  # noqa: ASYNC230 - tiny local test fixture
            assert json.load(saved)["data"] == budget.history
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_identity_during_subscription_can_be_answered(mqtt_api):
    client = make_test_instance(cached_devices=make_dummy_cached_devices())

    async def subscribe(hass, topic, callback, **kwargs):
        if topic.startswith("master/"):
            await callback(
                message(
                    {
                        "mi": "early",
                        "mt": "C",
                        "pl": {
                            "Cmd": "Identity",
                            "Id": "A1B2C3D4E5F6",
                            "Security": "test-only",
                        },
                    }
                )
            )
        return MagicMock()

    mqtt_api.async_subscribe.side_effect = subscribe
    try:
        await client.connect()
        sent = [
            json.loads(call.args[2]) for call in mqtt_api.async_publish.call_args_list
        ]
        assert any(p["mt"] == "A" and p["mi"] == "early" for p in sent)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_shared_mqtt_reconnect_requires_a_new_identity(mqtt_api):
    client = make_test_instance(cached_devices=make_dummy_cached_devices())
    await client.connect()
    client._identity_ready.set()
    callback = mqtt_api.async_subscribe_connection_status.call_args.args[1]
    callback(False)
    assert not client._identity_ready.is_set()
    callback(True)
    mqtt_api.async_publish.reset_mock()
    client.buffer_read_timeout = 0.01
    with pytest.raises(local_mqtt_module.AguaIOTConnectionError):
        await client._fetch_device_information(client.devices[0])
    commands = [
        json.loads(call.args[2])["pl"]["Cmd"]
        for call in mqtt_api.async_publish.call_args_list
    ]
    assert commands == ["Identity"]
    await client.close()
    mqtt_api.async_subscribe_connection_status.return_value.assert_called_once()


@pytest.mark.asyncio
async def test_two_stoves_keep_registers_and_endpoints_separate(mqtt_api):
    import copy

    cached = make_dummy_cached_devices()
    second = copy.deepcopy(cached[0])
    second.update(id_device="DEV_02", mac="112233445566")
    cached.append(second)
    mqtt_api.async_subscribe.side_effect = lambda *args, **kwargs: MagicMock()
    client = make_test_instance(cached_devices=cached)
    client.eeprom_limits = {"max_eeprom_writes_per_day": 25}
    try:
        await client.connect()
        first, second = client._children
        await first._message_received(
            message(
                {
                    "mt": "R",
                    "pl": {"Cmd": "RequestReading", "Items": [1], "Values": [240]},
                }
            )
        )
        assert first._register_values[1] == 240
        assert 1 not in second._register_values
        assert first.eeprom_limits == second.eeprom_limits == client.eeprom_limits
        assert [child._device_mac for child in client._children] == [
            "A1B2C3D4E5F6",
            "112233445566",
        ]
    finally:
        await client.close()


def test_cached_bit_fields_preserve_all_bits_at_a_shared_offset():
    client = make_test_instance()
    client._seed_register_cache_from_map(
        {
            "first": {"offset": 32768, "mask": 1, "value_raw": "1"},
            "second": {"offset": 32768, "mask": 2, "value_raw": "2"},
        }
    )
    assert client._register_values[32768] == 3
