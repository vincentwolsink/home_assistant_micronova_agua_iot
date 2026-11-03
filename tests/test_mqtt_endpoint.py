"""Client lifecycle and optional application receipts for generic MQTT endpoints."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aiomqtt
import pytest

from tests.helpers import load_component_module

module = load_component_module("mqtt_endpoint")


class FakeClient:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.subscribe = AsyncMock()
        self.publish = AsyncMock()
        self.__aenter__ = AsyncMock(return_value=self)
        self.__aexit__ = AsyncMock()

    @property
    def messages(self):
        async def receive():
            while True:
                item = await self.queue.get()
                if isinstance(item, Exception):
                    raise item
                yield item

        return receive()


@pytest.mark.asyncio
async def test_client_dispatch_and_clean_close(monkeypatch):
    raw = FakeClient()
    monkeypatch.setattr(module.aiomqtt, "Client", MagicMock(return_value=raw))
    adapter = module.MqttEndpoint(MagicMock(), {"hostname": "127.0.0.1"}, AsyncMock())
    callback = AsyncMock()
    await adapter.start()
    unsubscribe = await adapter.async_subscribe(None, "navel/AABBCCDDEEFF", callback)
    await raw.queue.put(
        SimpleNamespace(topic="navel/AABBCCDDEEFF", payload=b"live", retain=False)
    )
    async with asyncio.timeout(1):
        while not callback.called:
            await asyncio.sleep(0.01)
    assert callback.call_args.args[0].payload == b"live"
    await adapter.async_publish(None, "navel/AABBCCDDEEFF", "command")
    raw.publish.assert_awaited_once_with(
        "navel/AABBCCDDEEFF", "command", qos=0, retain=False
    )
    unsubscribe()
    assert adapter._callbacks == {}
    await adapter.close()
    await adapter.close()
    raw.__aexit__.assert_awaited_once()
    assert not adapter.is_connected(None)


@pytest.mark.asyncio
async def test_reconnect_resubscribes_and_reauthenticates(monkeypatch):
    first, second = FakeClient(), FakeClient()
    monkeypatch.setattr(
        module.aiomqtt, "Client", MagicMock(side_effect=[first, second])
    )
    monkeypatch.setattr(module, "RECONNECT_DELAY", 0.01)
    on_reconnect = AsyncMock()
    adapter = module.MqttEndpoint(MagicMock(), {}, on_reconnect)
    await adapter.start()
    await adapter.async_subscribe(None, "navel/AABBCCDDEEFF", AsyncMock())
    await first.queue.put(aiomqtt.MqttError("connection lost"))
    async with asyncio.timeout(1):
        while not on_reconnect.called:
            await asyncio.sleep(0.01)
    first.__aexit__.assert_awaited_once()
    second.subscribe.assert_awaited_once_with("navel/AABBCCDDEEFF", qos=0)
    # No pending control command is replayed when the connection returns.
    second.publish.assert_not_awaited()
    await adapter.close()
    second.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_reauthentication_retries_without_losing_reader(monkeypatch):
    first, second, third = FakeClient(), FakeClient(), FakeClient()
    monkeypatch.setattr(
        module.aiomqtt, "Client", MagicMock(side_effect=[first, second, third])
    )
    monkeypatch.setattr(module, "RECONNECT_DELAY", 0.001)
    on_reconnect = AsyncMock(side_effect=[module.AguaIOTError("publish failed"), None])
    adapter = module.MqttEndpoint(MagicMock(), {}, on_reconnect)
    callback = AsyncMock()
    try:
        await adapter.start()
        await adapter.async_subscribe(None, "navel/AABBCCDDEEFF", callback)
        await first.queue.put(aiomqtt.MqttError("connection lost"))
        async with asyncio.timeout(1):
            while on_reconnect.await_count < 2:
                await asyncio.sleep(0.001)
        await third.queue.put(
            SimpleNamespace(topic="navel/AABBCCDDEEFF", payload=b"live", retain=False)
        )
        async with asyncio.timeout(1):
            while not callback.called:
                await asyncio.sleep(0.001)
        assert adapter.is_connected(None)
        second.__aexit__.assert_awaited_once()
    finally:
        await adapter.close()
    third.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_endpoint_denial_reaches_control_caller(monkeypatch):
    import json

    raw = FakeClient()
    monkeypatch.setattr(module.aiomqtt, "Client", MagicMock(return_value=raw))
    adapter = module.MqttEndpoint(MagicMock(), {}, AsyncMock(), write_confirmation=True)
    await adapter.start()
    task = asyncio.create_task(
        adapter.async_publish(
            None,
            "navel/AABBCCDDEEFF",
            json.dumps(
                {"mi": "write-test", "mt": "Q", "pl": {"Cmd": "RequestWriting"}}
            ),
        )
    )
    try:
        async with asyncio.timeout(1):
            while not raw.publish.called:
                await asyncio.sleep(0)
        await raw.queue.put(
            SimpleNamespace(
                topic="master/responses/navel/AABBCCDDEEFF",
                retain=False,
                payload=json.dumps(
                    {
                        "mi": "write-test",
                        "mt": "G",
                        "pl": {
                            "Cmd": "MqttWriteResult",
                            "Accepted": False,
                            "Reason": "EEPROM writes disabled",
                        },
                    }
                ).encode(),
            )
        )
        with pytest.raises(module.HomeAssistantError, match="EEPROM writes disabled"):
            await asyncio.wait_for(task, 1)
        assert adapter._write_receipts == {}
    finally:
        await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("message_id", [None, [], {}, "", 42])
async def test_invalid_write_id_is_rejected_before_publish(message_id):
    import json

    adapter = module.MqttEndpoint(MagicMock(), {}, AsyncMock(), write_confirmation=True)
    adapter._client = FakeClient()
    with pytest.raises(module.HomeAssistantError, match="message ID"):
        await adapter.async_publish(
            None,
            "navel/test",
            json.dumps({"mi": message_id, "pl": {"Cmd": "RequestWriting"}}),
        )
    adapter._client.publish.assert_not_awaited()
    assert adapter._write_receipts == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("disconnect", [True, False])
async def test_pending_write_fails_promptly_on_disconnect_or_close(
    monkeypatch, disconnect
):
    import json

    raw = FakeClient()
    monkeypatch.setattr(module.aiomqtt, "Client", MagicMock(return_value=raw))
    adapter = module.MqttEndpoint(MagicMock(), {}, AsyncMock(), write_confirmation=True)
    await adapter.start()
    task = asyncio.create_task(
        adapter.async_publish(
            None,
            "navel/test",
            json.dumps({"mi": "pending", "pl": {"Cmd": "RequestWriting"}}),
        )
    )
    try:
        async with asyncio.timeout(1):
            while not raw.publish.called:
                await asyncio.sleep(0)
        if disconnect:
            await raw.queue.put(aiomqtt.MqttError("lost"))
        else:
            await adapter.close()
        with pytest.raises(module.HomeAssistantError, match="Delivery is uncertain"):
            await asyncio.wait_for(task, 1)
        assert adapter._write_receipts == {}
        assert raw.publish.await_count == 1
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_standard_broker_does_not_require_custom_write_receipts():
    import json

    raw = FakeClient()
    adapter = module.MqttEndpoint(MagicMock(), {}, AsyncMock())
    adapter._client = raw
    await adapter.async_publish(
        None,
        "navel/test",
        json.dumps({"mi": "write", "mt": "Q", "pl": {"Cmd": "RequestWriting"}}),
    )
    raw.publish.assert_awaited_once()
    assert adapter._write_receipts == {}
    await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "topic,retained,accepted",
    [
        ("master/responses/navel/OTHER", False, True),
        ("master/responses/navel/AABBCCDDEEFF", True, True),
        ("master/responses/navel/AABBCCDDEEFF", False, "true"),
    ],
)
async def test_invalid_receipt_does_not_complete_a_write(
    monkeypatch, topic, retained, accepted
):
    import json

    raw = FakeClient()
    monkeypatch.setattr(module.aiomqtt, "Client", MagicMock(return_value=raw))
    adapter = module.MqttEndpoint(MagicMock(), {}, AsyncMock(), write_confirmation=True)
    await adapter.start()
    task = asyncio.create_task(
        adapter.async_publish(
            None,
            "navel/AABBCCDDEEFF",
            json.dumps({"mi": "receipt-test", "pl": {"Cmd": "RequestWriting"}}),
        )
    )
    try:
        async with asyncio.timeout(1):
            while not raw.publish.called:
                await asyncio.sleep(0)
        await raw.queue.put(
            SimpleNamespace(
                topic=topic,
                retain=retained,
                payload=json.dumps(
                    {
                        "mi": "receipt-test",
                        "mt": "G",
                        "pl": {"Cmd": "MqttWriteResult", "Accepted": accepted},
                    }
                ),
            )
        )
        # A following regular message proves the reader consumed the invalid receipt.
        seen = asyncio.Event()

        async def received(_message):
            seen.set()

        await adapter.async_subscribe(None, "sentinel", received)
        await raw.queue.put(
            SimpleNamespace(topic="sentinel", retain=False, payload=b"{}")
        )
        await asyncio.wait_for(seen.wait(), 1)
        assert not task.done()
        await raw.queue.put(
            SimpleNamespace(
                topic="master/responses/navel/AABBCCDDEEFF",
                retain=False,
                payload=json.dumps(
                    {
                        "mi": "receipt-test",
                        "mt": "G",
                        "pl": {"Cmd": "MqttWriteResult", "Accepted": True},
                    }
                ),
            )
        )
        await asyncio.wait_for(task, 1)
    finally:
        await adapter.close()
