"""Local MQTT transport for Micronova Navel stoves."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import uuid
from typing import Any

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.importlib import async_import_module

from .aguaiot import (
    AguaIOTConnectionError,
    AguaIOTError,
    Device,
    aguaiot,
    update_devices,
)
from .eeprom import (
    EEPROM_OFFSET_THRESHOLD,
    clean_mac,
    reserve_device_write,
)
from .mqtt_endpoint import MqttEndpoint
from .register_overrides import apply_register_overrides

_LOGGER = logging.getLogger(__name__)


ACTIVE_EEPROM_PREFIXES = ("chrono_p",)


class LocalMqttSetupError(AguaIOTConnectionError):
    """A local setup problem with a user-facing config flow error key."""

    def __init__(self, key: str, message: str):
        super().__init__(message)
        self.key = key


class LocalMqttAguaIOT:
    """Manage stove sessions and register access over MQTT."""

    def __init__(
        self,
        hass: Any,
        api_url: str,
        customer_code: str,
        email: str,
        password: str,
        unique_id: str,
        *,
        login_api_url: str | None = None,
        brand_id: str | None = None,
        brand: str | None = None,
        application_version: str = "1.9.7",
        async_client=None,
        air_temp_fix: bool = False,
        language: str | None = "ENG",
        http_timeout: int = 30,
        buffer_read_timeout: int = 30,
        mqtt_settings: dict | None = None,
        eeprom_limits: dict | None = None,
        cached_devices: list[dict[str, Any]] | None = None,
    ) -> None:
        self.hass = hass
        self.api_url = api_url.rstrip("/")
        self.customer_code = customer_code
        self.email = email
        self.password = password
        self.unique_id = unique_id
        self.login_api_url = login_api_url
        self.brand_id = brand_id
        self.brand = brand
        self.application_version = application_version
        self.async_client = async_client
        self.air_temp_fix = air_temp_fix
        self.language = language
        self.http_timeout = http_timeout
        self.buffer_read_timeout = buffer_read_timeout
        self.devices: list[Device] = []

        self._session_uuid = str(uuid.uuid4()).upper()
        self._mqtt_settings = mqtt_settings or {}
        self.eeprom_limits = eeprom_limits or {}
        self._cached_devices = cached_devices or []
        self._cache_dirty = False
        self._children = []

        self._unsubscribe = None
        self._unsubscribe_connection = None
        self._mqtt = None
        self._owns_mqtt = False
        self._read_generation = 0
        self._device_mac: str | None = None
        self._security_code: str | None = None
        self._register_values: dict[int, int] = {}
        self._response_event = asyncio.Event()
        self._identity_ready = asyncio.Event()
        self._identity_pending = False
        self._read_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()

    @property
    def cache_dirty(self) -> bool:
        """Return True when bootstrap cache should be persisted."""
        return self._cache_dirty or any(child.cache_dirty for child in self._children)

    def export_bootstrap_cache(self) -> list[dict[str, Any]]:
        """Export device bootstrap data for config entry persistence."""
        return [device.export_cache() for device in self.devices]

    def mark_cache_persisted(self) -> None:
        """Clear the dirty flag once bootstrap data is stored."""
        self._cache_dirty = False
        for child in self._children:
            child.mark_cache_persisted()

    def _clean_identifier(self, raw_id: str | None) -> str | None:
        """Strip colons and dashes from MAC or serial identifiers."""
        if not isinstance(raw_id, str) or not raw_id:
            return None
        return raw_id.replace(":", "").replace("-", "").strip().upper()

    def _seed_register_cache_from_map(
        self, register_map: dict[str, Any] | None
    ) -> None:
        """Pre-populate initial register values from the persisted bootstrap register map."""
        if not isinstance(register_map, dict):
            return
        for reg in register_map.values():
            if not isinstance(reg, dict) or "offset" not in reg:
                continue
            offset = int(reg["offset"])
            raw_val = reg.get("value_raw")
            if raw_val is not None:
                try:
                    self._register_values[offset] = self._register_values.get(
                        offset, 0
                    ) | (int(raw_val) & int(reg.get("mask", 65535)))
                except (ValueError, TypeError):
                    pass

    def _load_cached_devices(self, cached_devices: list[dict[str, Any]]) -> None:
        """Restore devices from persisted bootstrap cache."""
        self.devices = []
        for entry in cached_devices:
            reg_map = apply_register_overrides(
                entry["id_registers_map"],
                entry.get("register_map") or entry.get("registers"),
            )
            self._seed_register_cache_from_map(reg_map)
            dev = Device(
                entry["id"],
                entry["id_device"],
                entry["id_product"],
                entry["product_serial"],
                entry["name"],
                entry.get("is_online", True),
                entry.get("name_product", "Pellet Stove"),
                entry["id_registers_map"],
                self,
                device_info=entry.get("device_info"),
                register_map=reg_map,
                mac=entry.get("mac"),
            )
            self.devices.append(dev)

            if not self._device_mac:
                self._device_mac = clean_mac(dev.wifi_mac)

            if not self._security_code:
                dev_info = entry.get("device_info") or {}
                self._security_code = dev_info.get("reg_code") or dev_info.get(
                    "security_code"
                )

    async def _bootstrap_from_cloud(self) -> None:
        """Fetch device metadata and register mappings once via the cloud API."""
        cloud = aguaiot(
            api_url=self.api_url,
            customer_code=self.customer_code,
            email=self.email,
            password=self.password,
            unique_id=self.unique_id,
            login_api_url=self.login_api_url,
            brand_id=self.brand_id,
            brand=self.brand,
            application_version=self.application_version,
            async_client=self.async_client,
            air_temp_fix=self.air_temp_fix,
            language=self.language,
            http_timeout=self.http_timeout,
            buffer_read_timeout=self.buffer_read_timeout,
        )
        await cloud.connect()

        self.devices = []
        for dev in cloud.devices:
            reg_map = apply_register_overrides(
                dev.id_registers_map, dev.export_register_map()
            )
            self._seed_register_cache_from_map(reg_map)
            self.devices.append(
                Device(
                    dev.id,
                    dev.id_device,
                    dev.id_product,
                    dev.product_serial,
                    dev.name,
                    dev.is_online,
                    dev.name_product,
                    dev.id_registers_map,
                    self,
                    device_info=dev.device_info_data,
                    register_map=reg_map,
                    mac=dev.wifi_mac,
                )
            )
        self._cache_dirty = True

        for dev in self.devices:
            if not self._device_mac:
                self._device_mac = clean_mac(dev.wifi_mac)
            if not self._security_code:
                dev_info = dev.device_info_data or {}
                self._security_code = dev_info.get("reg_code") or dev_info.get(
                    "security_code"
                )

    async def _fetch_device_registers_mapping(self, device: Device) -> dict[str, Any]:
        """Return the cached registers map."""
        register_map = device.export_register_map()
        if register_map:
            return register_map
        raise AguaIOTError(f"No cached registers map found for '{device.name}'")

    async def connect(self) -> None:
        """Load stove metadata and establish MQTT subscriptions."""
        if self._children:
            return
        if len(self._cached_devices) > 1:
            await self._connect_children(self._cached_devices)
            return
        if self._cached_devices:
            self._load_cached_devices(self._cached_devices)
        else:
            await self._bootstrap_from_cloud()
            if len(self.devices) > 1:
                await self._connect_children(self.export_bootstrap_cache())
                return

        if not self.devices:
            raise AguaIOTConnectionError(
                "No cached stoves are available for local MQTT."
            )

        try:
            await self._subscribe()
            # A stove may already be connected when HA starts.
            if self._device_mac and self._security_code:
                await self._authenticate()
        except LocalMqttSetupError:
            await self.close()
            raise
        except (
            AguaIOTError,
            HomeAssistantError,
            OSError,
            RuntimeError,
            ValueError,
        ) as err:
            await self.close()
            raise AguaIOTConnectionError(
                "Could not initialize Home Assistant MQTT for Navel."
            ) from err

    async def _connect_children(self, cached_devices):
        """Create a separate MQTT session for each cached stove."""
        self.devices = []
        try:
            for cached in cached_devices:
                child = LocalMqttAguaIOT(
                    hass=self.hass,
                    api_url=self.api_url,
                    customer_code=self.customer_code,
                    email=self.email,
                    password=self.password,
                    unique_id=self.unique_id,
                    login_api_url=self.login_api_url,
                    brand_id=self.brand_id,
                    brand=self.brand,
                    application_version=self.application_version,
                    async_client=self.async_client,
                    air_temp_fix=self.air_temp_fix,
                    language=self.language,
                    http_timeout=self.http_timeout,
                    buffer_read_timeout=self.buffer_read_timeout,
                    mqtt_settings=self._mqtt_settings,
                    eeprom_limits=self.eeprom_limits,
                    cached_devices=[cached],
                )
                self._children.append(child)
                await child.connect()
                self.devices.extend(child.devices)
            macs = [child._device_mac for child in self._children]
            if len(set(macs)) != len(macs):
                raise AguaIOTConnectionError(
                    "Duplicate stove MAC addresses in the device cache."
                )
        except (Exception, asyncio.CancelledError):
            await self.close()
            raise

    async def _subscribe(self) -> None:
        """Subscribe using the configured endpoint or Home Assistant MQTT."""
        if self._unsubscribe is not None:
            return
        settings = self._mqtt_settings
        if not self._device_mac:
            raise LocalMqttSetupError(
                "invalid_mac",
                "The cloud did not provide a Wi-Fi MAC address for this stove.",
            )
        if settings.get("hostname"):
            info = {
                key: settings[key]
                for key in ("hostname", "port", "username", "password")
                if key in settings
            }
            self._mqtt = MqttEndpoint(
                self.hass,
                info,
                self._on_mqtt_reconnect,
                on_disconnect=self._on_mqtt_disconnect,
            )
            self._owns_mqtt = True
            await self._mqtt.start()
        else:
            mqtt = await async_import_module(self.hass, "homeassistant.components.mqtt")

            if not await mqtt.async_wait_for_mqtt_client(self.hass):
                raise LocalMqttSetupError(
                    "mqtt_unavailable",
                    "Configure Home Assistant MQTT or an MQTT endpoint.",
                )
            self._mqtt = mqtt
            self._unsubscribe_connection = mqtt.async_subscribe_connection_status(
                self.hass, self._mqtt_connection_changed
            )
        # Firmware variants publish responses on either of these stove topics.
        subscriptions = []
        try:
            for topic in (
                f"navel/{self._device_mac}",
                f"master/responses/navel/{self._device_mac}",
            ):
                subscriptions.append(
                    await self._mqtt.async_subscribe(
                        self.hass, topic, self._message_received, qos=0
                    )
                )
        except (HomeAssistantError, OSError, RuntimeError, ValueError):
            for unsubscribe in subscriptions:
                unsubscribe()
            raise

        def unsubscribe_all():
            for unsubscribe in subscriptions:
                unsubscribe()

        self._unsubscribe = unsubscribe_all

    async def fetch_device_information(self) -> None:
        """Fetch information for all devices."""
        for dev in self.devices:
            await dev.update_mapping()

    async def update(self) -> None:
        """Poll the stove for latest readings and update device states."""
        await update_devices(self.devices)

    async def validate_local_connection(self) -> dict[str, Any]:
        """Require a fresh register reading from each stove."""
        if self._children:
            results = await asyncio.gather(
                *(child.validate_local_connection() for child in self._children),
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, BaseException):
                    raise result
            return {"device_macs": [result["device_mac"] for result in results]}
        if not self.devices:
            raise AguaIOTError("No Micronova devices are available for local MQTT.")

        if self._unsubscribe is None or not self._mqtt.is_connected(self.hass):
            raise AguaIOTConnectionError("Home Assistant MQTT is not connected.")

        generation = self._read_generation
        try:
            await self._fetch_device_information(self.devices[0])
        except AguaIOTConnectionError as err:
            raise LocalMqttSetupError(
                "stove_not_responding",
                "No live reading received from the stove. Check its network connection.",
            ) from err
        if self._read_generation == generation:
            raise LocalMqttSetupError(
                "stove_not_responding",
                "No live reading received from the stove. Check its IP, the vendor hostname "
                "redirect, and the MQTT connection.",
            )
        return {"device_mac": self._device_mac}

    def _collect_readable_offsets(self, device: Device) -> list[int]:
        """Collect RAM and active setpoint/status offsets to read from the stove."""
        register_map = device.export_register_map() or {}
        offsets: set[int] = set()

        for key, reg in register_map.items():
            if not isinstance(reg, dict) or "offset" not in reg:
                continue
            offset = int(reg["offset"])
            reg_type = reg.get("reg_type")
            key_lower = str(key).lower()

            if (
                offset < EEPROM_OFFSET_THRESHOLD
                or reg_type in ("GET", "ENABLE", "SET")
                and not key_lower.startswith(ACTIVE_EEPROM_PREFIXES)
            ):
                offsets.add(offset)

        if not offsets:
            raise AguaIOTError("The stove register map contains no readable offsets.")

        return sorted(offsets)

    def _collect_word_offsets(self, device: Device) -> set[int]:
        """Collect offsets of 16-bit registers, read as words like the cloud buffer."""
        register_map = device.export_register_map() or {}
        return {
            int(reg["offset"])
            for reg in register_map.values()
            if isinstance(reg, dict) and "offset" in reg and reg.get("is_word")
        }

    async def _fetch_device_information(self, device: Device) -> dict[int, int]:
        """Serialize reads sharing the firmware response event."""
        async with self._read_lock:
            return await self._fetch_device_information_locked(device)

    async def _fetch_device_information_locked(self, device: Device) -> dict[int, int]:
        """Query registers from the stove over local MQTT."""
        if self._unsubscribe is None or not self._mqtt.is_connected(self.hass):
            raise AguaIOTConnectionError("Stove is not connected via local MQTT.")
        await self._await_stove_identity()

        target_offsets = self._collect_readable_offsets(device)
        word_offsets = self._collect_word_offsets(device)

        self._response_event.clear()
        masks = [65535] * len(target_offsets)
        query = {
            "mi": str(uuid.uuid4()),
            "mt": "Q",
            "r": {"rj": "Navel"},
            "s": {"ss": "Apk", "sj": self._session_uuid},
            "pl": {
                "Cmd": "RequestReading",
                "Items": target_offsets,
                "Masks": masks,
                # Without BitData the module returns only the low byte, which
                # drops enable bits above 0xFF (e.g. canalization_sx_enable).
                "BitData": [
                    16 if offset in word_offsets else 8 for offset in target_offsets
                ],
                "Endianess": ["L"] * len(target_offsets),
            },
        }

        target_mac = self._device_mac
        try:
            await self._send_mqtt_publish(f"navel/{target_mac}", query)
            await asyncio.wait_for(
                self._response_event.wait(),
                timeout=self.buffer_read_timeout,
            )
        except TimeoutError as err:
            raise AguaIOTConnectionError(
                "No live reading received from the stove."
            ) from err
        except (OSError, RuntimeError, AguaIOTError) as err:
            raise AguaIOTConnectionError("Could not read stove registers.") from err

        return copy.deepcopy(self._register_values)

    async def _request_writing(
        self, device: Device, payload_or_items: dict[str, Any]
    ) -> None:
        """Send a register write command without automatic retries."""
        if self._unsubscribe is None or not self._mqtt.is_connected(self.hass):
            raise AguaIOTConnectionError("Stove is not connected via local MQTT.")

        if "Cmd" not in payload_or_items:
            item_offsets = []
            masks = []
            bit_data = []
            values = []

            for key, value in payload_or_items.items():
                register = device.get_register(key)
                mask = int(register["mask"])
                item_offsets.append(int(register["offset"]))
                masks.append(mask)
                bit_data.append(16 if mask > 0xFF else 8)
                values.append(int(value))

            payload = {
                "Cmd": "RequestWriting",
                "Protocol": "RWMSmaster",
                "BitData": bit_data,
                "Endianess": ["L"] * len(item_offsets),
                "Items": item_offsets,
                "Masks": masks,
                "Values": values,
            }
        else:
            payload = payload_or_items
            item_offsets = [int(x) for x in payload.get("Items", [])]

        target_mac = self._device_mac
        async with self._write_lock:
            await self._await_stove_identity()
            await reserve_device_write(
                self.hass,
                device,
                item_offsets,
                explicit_mac=target_mac,
                limits=self.eeprom_limits,
            )
            cmd = {
                "mi": str(uuid.uuid4()),
                "mt": "Q",
                "r": {"rj": "Navel"},
                "s": {"ss": "Apk", "sj": self._session_uuid},
                "pl": payload,
            }
            await self._send_mqtt_publish(f"navel/{target_mac}", cmd)
            await asyncio.sleep(0.5)
            await self._fetch_device_information(device)

    async def _send_mqtt_publish(self, topic: str, data: dict[str, Any]) -> None:
        """Publish a non-retained Navel command."""
        # Identity announcements can arrive before all subscriptions are established.
        if self._mqtt is None or not self._mqtt.is_connected(self.hass):
            raise AguaIOTConnectionError("Home Assistant MQTT is not connected.")
        try:
            await self._mqtt.async_publish(
                self.hass, topic, json.dumps(data), qos=0, retain=False
            )
        except HomeAssistantError as err:
            raise AguaIOTConnectionError(
                f"Could not publish a Navel command: {err}"
            ) from err

    async def _await_stove_identity(self) -> None:
        """Wait for the stove to complete authentication."""
        if self._identity_ready.is_set():
            return
        try:
            if not self._identity_pending:
                await self._authenticate()
            await asyncio.wait_for(
                self._identity_ready.wait(),
                timeout=self.buffer_read_timeout,
            )
        except TimeoutError as err:
            self._identity_pending = False
            raise AguaIOTConnectionError(
                "No live reading received from the stove."
            ) from err

    @callback
    def _mqtt_connection_changed(self, connected: bool) -> None:
        """Reauthenticate on the next poll after a shared MQTT reconnect."""
        self._identity_ready.clear()
        self._identity_pending = False

    async def _on_mqtt_disconnect(self) -> None:
        """Clear authentication state after disconnecting."""
        self._identity_ready.clear()
        self._identity_pending = False

    async def _on_mqtt_reconnect(self) -> None:
        """Authenticate after reconnecting to the MQTT endpoint."""
        self._identity_ready.clear()
        self._identity_pending = False
        await self._authenticate()

    async def _authenticate(self) -> None:
        """Authenticate the application session using the stove registration code."""
        self._identity_pending = True
        await self._send_mqtt_publish(
            f"navel/{self._device_mac}",
            {
                "mi": str(uuid.uuid4()),
                "mt": "Q",
                "r": {"rj": "Navel"},
                "s": {"ss": "Apk", "sj": self._session_uuid},
                "pl": {
                    "Cmd": "Identity",
                    "Id": self._device_mac,
                    "Security": self._security_code or "",
                },
            },
        )

    async def _message_received(self, message) -> None:
        """Handle live stove messages, ignoring retained traffic and our own commands."""
        if message.retain:
            return
        try:
            obj = json.loads(message.payload)
        except (ValueError, TypeError, UnicodeError):
            _LOGGER.debug("Ignoring malformed Navel JSON message")
            return
        if not isinstance(obj, dict) or obj.get("mt") not in ("C", "R"):
            return
        sender = obj.get("s", {})
        if not isinstance(sender, dict):
            return
        if sender.get("sj") == self._session_uuid:
            return
        pl = obj.get("pl")
        if not isinstance(pl, dict):
            return
        cmd = pl.get("Cmd") or pl.get("cmd")
        if cmd == "Identity" and obj.get("mt") == "C":
            if "Id" in pl and not isinstance(pl["Id"], str):
                return
            identity = self._clean_identifier(pl.get("Id"))
            if identity and identity != self._device_mac:
                return
            # A new Identity announcement starts a fresh authentication exchange.
            self._identity_ready.clear()
            self._identity_pending = False
            if pl.get("Security"):
                self._security_code = str(pl["Security"])
                for device in self.devices:
                    if device.device_info_data.get("reg_code") != self._security_code:
                        device.device_info_data["reg_code"] = self._security_code
                        self._cache_dirty = True
            await self._send_mqtt_publish(
                f"navel/{self._device_mac}",
                {
                    "mi": obj.get("mi", str(uuid.uuid4())),
                    "mt": "A",
                    "r": {"rj": "Navel", "rs": "XM"},
                    "s": {"ss": "Apk", "sj": self._session_uuid},
                    "pl": {"cmd": "Identity", "Success": True, "Result": 0},
                },
            )
            await self._authenticate()
        elif cmd == "Identity" and obj.get("mt") == "R":
            self._identity_pending = False
            self._identity_ready.clear()
            if pl.get("Result", 0) == 0 and pl.get("Success", True) is True:
                self._identity_ready.set()
        elif cmd == "Ping" and obj.get("mt") == "C":
            await self._send_mqtt_publish(
                f"navel/{self._device_mac}",
                {
                    "mi": obj.get("mi", str(uuid.uuid4())),
                    "mt": "A",
                    "r": {"rj": "Navel", "rs": "XM"},
                    "s": {"ss": "Apk", "sj": self._session_uuid},
                    "pl": {"cmd": "Ping", "Success": True},
                },
            )
        elif cmd == "RequestReading" and obj.get("mt") == "R":
            items = pl.get("Items", pl.get("items"))
            values = pl.get("Values", pl.get("values"))
            if (
                not isinstance(items, list)
                or not items
                or not isinstance(values, list)
                or len(items) != len(values)
            ):
                return
            try:
                readings = {
                    int(item): int(value)
                    for item, value in zip(items, values, strict=True)
                }
            except (TypeError, ValueError, OverflowError):
                return
            self._register_values.update(readings)
            self._read_generation += 1
            self._response_event.set()

    async def close(self) -> None:
        """Remove subscriptions and close owned MQTT connections."""
        children, self._children = self._children, []
        if children:
            await asyncio.gather(*(child.close() for child in children))
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._unsubscribe_connection is not None:
            self._unsubscribe_connection()
            self._unsubscribe_connection = None
        self._identity_ready.clear()
        self._identity_pending = False
        if self._owns_mqtt:
            await self._mqtt.close()
            self._owns_mqtt = False
