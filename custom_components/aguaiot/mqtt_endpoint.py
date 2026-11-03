"""MQTT client for an explicitly configured endpoint."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import suppress
from types import SimpleNamespace

import aiomqtt
from homeassistant.exceptions import HomeAssistantError

from .aguaiot import AguaIOTError

_LOGGER = logging.getLogger(__name__)
RECONNECT_DELAY = 2


class MqttEndpoint:
    """Manage subscriptions, reconnects and optional write confirmations."""

    def __init__(
        self,
        hass,
        connection_info: dict,
        on_reconnect,
        *,
        on_disconnect=None,
        write_confirmation=False,
    ):
        self._write_confirmation = write_confirmation
        self.hass = hass
        self._info = connection_info
        self._on_reconnect = on_reconnect
        self._on_disconnect = on_disconnect
        self._client = None
        self._callbacks = {}
        self._reader_task = None
        self._closing = False
        self._write_receipts = {}
        self._identifier = f"navel-user-{uuid.uuid4().hex}"

    async def _connect(self):
        client = aiomqtt.Client(**self._info, identifier=self._identifier)
        try:
            await client.__aenter__()
        except aiomqtt.MqttError as err:
            raise HomeAssistantError(
                "Cannot connect to the optional MQTT endpoint"
            ) from err
        self._client = client
        return client

    async def start(self):
        client = await self._connect()
        self._reader_task = asyncio.create_task(self._listen(client))

    def is_connected(self, _hass):
        return self._client is not None and not self._closing

    async def async_subscribe(self, _hass, topic, callback, qos=0):
        if self._client is None:
            raise HomeAssistantError("MQTT endpoint is disconnected")
        self._callbacks[topic] = callback
        try:
            await self._client.subscribe(topic, qos=qos)
        except aiomqtt.MqttError as err:
            self._callbacks.pop(topic, None)
            raise HomeAssistantError("Cannot subscribe to the MQTT endpoint") from err
        # Closing this client discards its subscriptions through MQTT clean-session.
        return lambda: self._callbacks.pop(topic, None)

    async def async_publish(self, _hass, topic, payload, qos=0, retain=False):
        if self._client is None:
            raise HomeAssistantError("MQTT endpoint is disconnected")
        # An application receipt reports whether the endpoint accepted the write.
        receipt = None
        message_id = None
        try:
            obj = json.loads(payload)
        except (ValueError, TypeError):
            obj = {}
        if (
            self._write_confirmation
            and isinstance(obj, dict)
            and isinstance(obj.get("pl"), dict)
            and obj["pl"].get("Cmd") == "RequestWriting"
        ):
            message_id = obj.get("mi")
            if not isinstance(message_id, str) or not message_id:
                raise HomeAssistantError(
                    "Write command requires a non-empty message ID"
                )
            if message_id in self._write_receipts:
                raise HomeAssistantError("Write command message ID is already pending")
            receipt = asyncio.get_running_loop().create_future()
            self._write_receipts[message_id] = (
                receipt,
                {topic, f"master/responses/{topic}"},
            )
        try:
            await self._client.publish(topic, payload, qos=qos, retain=retain)
            if receipt is not None:
                result = await asyncio.wait_for(receipt, 10)
                if result.get("Accepted") is not True:
                    raise HomeAssistantError(
                        result.get("Reason") or "MQTT endpoint blocked this write"
                    )
        except TimeoutError as err:
            raise HomeAssistantError(
                "No endpoint write confirmation. Delivery is uncertain; the command was not retried."
            ) from err
        except aiomqtt.MqttError as err:
            raise HomeAssistantError("Cannot publish to the MQTT endpoint") from err
        finally:
            if message_id is not None:
                self._write_receipts.pop(message_id, None)

    def _fail_pending_writes(self):
        for receipt, _topics in self._write_receipts.values():
            if not receipt.done():
                receipt.set_exception(
                    HomeAssistantError(
                        "Endpoint disconnected before write confirmation. Delivery is uncertain; the command was not retried."
                    )
                )
        self._write_receipts.clear()

    async def _listen(self, client):
        try:
            await self._listen_loop(client)
        finally:
            self._fail_pending_writes()
            active, self._client = self._client, None
            if active is not None:
                with suppress(aiomqtt.MqttError):
                    await active.__aexit__(None, None, None)

    async def _listen_loop(self, client):
        while not self._closing:
            try:
                async for message in client.messages:
                    try:
                        obj = json.loads(message.payload)
                    except (ValueError, TypeError, UnicodeError):
                        obj = None
                    if message.retain:
                        continue
                    if isinstance(obj, dict) and obj.get("mt") == "G":
                        message_id = obj.get("mi")
                        pending = (
                            self._write_receipts.get(message_id)
                            if isinstance(message_id, str)
                            else None
                        )
                        pl = obj.get("pl")
                        if (
                            pending is not None
                            and str(message.topic) in pending[1]
                            and not pending[0].done()
                            and isinstance(pl, dict)
                            and pl.get("Cmd") == "MqttWriteResult"
                            and type(pl.get("Accepted")) is bool
                        ):
                            pending[0].set_result(pl)
                        continue
                    callback = self._callbacks.get(str(message.topic))
                    if callback is not None:
                        await callback(
                            SimpleNamespace(
                                payload=message.payload, retain=message.retain
                            )
                        )
            except (aiomqtt.MqttError, HomeAssistantError, AguaIOTError, OSError):
                _LOGGER.debug("MQTT endpoint connection interrupted; reconnecting")
            finally:
                self._fail_pending_writes()
                self._client = None
                if not self._closing and self._on_disconnect is not None:
                    await self._on_disconnect()
                with suppress(aiomqtt.MqttError):
                    await client.__aexit__(None, None, None)
            while not self._closing:
                await asyncio.sleep(RECONNECT_DELAY)
                new_client = None
                try:
                    new_client = await self._connect()
                    client = new_client
                    for topic in tuple(self._callbacks):
                        await client.subscribe(topic, qos=0)
                    await self._on_reconnect()
                except (HomeAssistantError, aiomqtt.MqttError, AguaIOTError, OSError):
                    self._client = None
                    if new_client is not None:
                        with suppress(aiomqtt.MqttError):
                            await new_client.__aexit__(None, None, None)
                    continue
                break

    async def close(self):
        self._closing = True
        self._fail_pending_writes()
        self._callbacks.clear()
        if self._reader_task is not None:
            self._reader_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None
        if self._client is not None:
            client, self._client = self._client, None
            with suppress(aiomqtt.MqttError):
                await client.__aexit__(None, None, None)
