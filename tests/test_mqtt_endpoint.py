"""Client lifecycle for generic MQTT endpoints."""

import asyncio
import json
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
async def test_write_command_is_published_without_waiting_for_a_receipt():
    raw = FakeClient()
    adapter = module.MqttEndpoint(MagicMock(), {}, AsyncMock())
    adapter._client = raw
    payload = json.dumps({"mi": "write", "mt": "Q", "pl": {"Cmd": "RequestWriting"}})
    await adapter.async_publish(None, "navel/test", payload)
    raw.publish.assert_awaited_once_with("navel/test", payload, qos=0, retain=False)
    await adapter.close()
