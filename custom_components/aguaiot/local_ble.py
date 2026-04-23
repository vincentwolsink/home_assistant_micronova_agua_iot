"""Local Bluetooth transport for Micronova T009/Navel modules."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import struct
import uuid
from typing import Any

from bleak import BleakClient, BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .aguaiot import (
    AguaIOTConnectionError,
    AguaIOTError,
    AguaIOTUpdateError,
    Device,
    aguaiot,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
DEFAULT_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
DEFAULT_NAME_PREFIX = "T009_"
BLE_DISCOVERY_RETRY_INTERVAL = 1
BLE_DISCOVERY_MAX_WAIT = 30


def _is_ble_authorization_error(err: Exception) -> bool:
    """Return True when the BLE stack rejected the link for authorization reasons."""
    message = str(err).lower()
    return "insufficient authorization" in message or (
        "authorization" in message and "(8)" in message
    )


def _normalize_ble_address(value: str | None) -> str | None:
    """Return a colon-separated BLE address."""
    if not value:
        return None

    compact = re.sub(r"[^0-9A-Fa-f]", "", value)
    if len(compact) == 12:
        return ":".join(compact[i : i + 2] for i in range(0, 12, 2)).upper()

    return value.upper()


def _normalize_identity_id(value: str | None) -> str | None:
    """Return the Micronova identity id format used in BLE JSON commands."""
    if not value:
        return None

    compact = re.sub(r"[^0-9A-Fa-f]", "", value)
    if compact:
        return compact.upper()

    return value


def _increment_ble_address(value: str, delta: int) -> str:
    """Return a BLE address with the last byte incremented by delta."""
    compact = re.sub(r"[^0-9A-Fa-f]", "", value)
    if len(compact) != 12:
        return value.upper()

    last_byte = int(compact[-2:], 16)
    next_byte = (last_byte + delta) & 0xFF
    compact = f"{compact[:-2]}{next_byte:02X}"
    return ":".join(compact[i : i + 2] for i in range(0, 12, 2)).upper()


class LocalBleAguaIOT:
    """Micronova transport using the local BLE API exposed by the T009 module."""

    def __init__(
        self,
        hass: HomeAssistant,
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
        reading_error_fix: bool = False,
        language: str | None = "ENG",
        http_timeout: int | None = 30,
        buffer_read_timeout: int | None = 30,
        service_uuid: str = DEFAULT_SERVICE_UUID,
        char_uuid: str = DEFAULT_CHAR_UUID,
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
        self.reading_error_fix = reading_error_fix
        self.language = language
        self.http_timeout = http_timeout or 30
        self.buffer_read_timeout = buffer_read_timeout or 30
        self.service_uuid = service_uuid.lower()
        self.char_uuid = char_uuid.lower()
        self.devices: list[Device] = []

        self._session_uuid = str(uuid.uuid4()).upper()
        self._cached_devices = cached_devices or []
        self._cache_dirty = False
        self._command_lock = asyncio.Lock()

    @property
    def cache_dirty(self) -> bool:
        """Return True when bootstrap cache should be persisted."""
        return self._cache_dirty

    def export_bootstrap_cache(self) -> list[dict[str, Any]]:
        """Export device bootstrap data for config entry persistence."""
        return [device.export_cache() for device in self.devices]

    def mark_cache_persisted(self) -> None:
        """Clear the dirty flag once bootstrap data is stored."""
        self._cache_dirty = False

    async def connect(self) -> None:
        """Initialize devices from cache, or bootstrap once through the cloud API."""
        if self._cached_devices:
            self._load_cached_devices(self._cached_devices)
            return

        await self._bootstrap_from_cloud()

    async def fetch_device_information(self) -> None:
        """Compatibility helper with the cloud transport."""
        for dev in self.devices:
            await dev.update_mapping()

    async def update(self) -> None:
        """Refresh all devices using BLE."""
        for dev in self.devices:
            await dev.update()

    async def validate_local_connection(self) -> dict[str, Any]:
        """Detect and validate the local BLE module for the first configured stove."""
        if not self.devices:
            raise AguaIOTError(
                "No Micronova devices are available for local Bluetooth."
            )

        device = self.devices[0]
        result = await self._run_authenticated_session(
            device,
            "validating the local Bluetooth connection",
            self._validate_local_connection_session,
        )
        _LOGGER.info(
            "Validated Micronova BLE module for '%s' via %s (%s), buffer_ids=%s",
            device.name,
            result["module_address"],
            result["module_name"],
            result["buffer_ids"],
        )
        return result

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
            reading_error_fix=self.reading_error_fix,
            language=self.language,
            http_timeout=self.http_timeout,
            buffer_read_timeout=self.buffer_read_timeout,
        )
        await cloud.connect()

        self.devices = [
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
                register_map=dev.export_register_map(),
            )
            for dev in cloud.devices
        ]
        self._cache_dirty = True

    def _load_cached_devices(self, cached_devices: list[dict[str, Any]]) -> None:
        """Restore devices from persisted bootstrap cache."""
        self.devices = [
            Device(
                entry["id"],
                entry["id_device"],
                entry["id_product"],
                entry["product_serial"],
                entry["name"],
                entry["is_online"],
                entry["name_product"],
                entry["id_registers_map"],
                self,
                device_info=entry.get("device_info"),
                register_map=entry.get("register_map"),
            )
            for entry in cached_devices
        ]

    async def _fetch_device_registers_mapping(self, device: Device) -> dict[str, Any]:
        """Return the cached registers map."""
        register_map = device.export_register_map()
        if register_map:
            return register_map

        raise AguaIOTError(
            f"No cached register map available for '{device.name}'. Bootstrap through the cloud API first."
        )

    async def _fetch_device_information(self, device: Device) -> dict[int, int]:
        """Read all current buffer values from the stove over BLE."""
        return await self._run_authenticated_session(
            device,
            "reading device information",
            self._fetch_device_information_session,
        )

    async def _request_writing(self, device: Device, items: dict[str, int]) -> None:
        """Write raw register values to the stove over BLE."""
        item_offsets = []
        masks = []
        bit_data = []
        values = []

        for key, value in items.items():
            register = device.get_register(key)
            mask = int(register["mask"])
            item_offsets.append(int(register["offset"]))
            masks.append(mask)
            bit_data.append(16 if mask > 0xFF else 8)
            values.append(value)

        payload = {
            "Cmd": "RequestWriting",
            "Protocol": "RWMSmaster",
            "BitData": bit_data,
            "Endianess": ["L"] * len(item_offsets),
            "Items": item_offsets,
            "Masks": masks,
            "Values": values,
        }

        await self._run_authenticated_session(
            device,
            "writing stove registers",
            lambda session: self._request_writing_session(session, payload),
        )

    async def _validate_local_connection_session(
        self, session: "_BleMicronovaSession"
    ) -> dict[str, Any]:
        """Validate the BLE tunnel through an authenticated session."""
        buffer_ids = await session.get_buffer_ids()
        if not buffer_ids:
            raise AguaIOTUpdateError(
                f"Bluetooth validation succeeded but no buffer IDs were returned for '{session._device.name}'."
            )

        await session.get_buffer_reading(buffer_ids[0])
        return {
            "device_name": session._device.name,
            "module_address": session.connected_address
            or self._device_ble_address(session._device),
            "module_name": session.connected_name
            or self._expected_local_name(session._device),
            "buffer_ids": buffer_ids,
        }

    async def _fetch_device_information_session(
        self, session: "_BleMicronovaSession"
    ) -> dict[int, int]:
        """Read all current buffer values through an authenticated session."""
        buffer_ids = await session.get_buffer_ids()
        if not buffer_ids:
            buffer_ids = [1]

        info: dict[int, int] = {}
        for buffer_id in buffer_ids:
            response = await session.get_buffer_reading(buffer_id)
            payload = response.get("pl", {})
            items = payload.get("Items") or []
            values = payload.get("Values") or []
            if not isinstance(items, list) or not isinstance(values, list):
                continue

            for idx, item in enumerate(items):
                if idx < len(values):
                    info[item] = values[idx]

        if not info:
            raise AguaIOTUpdateError(
                f"Bluetooth read returned no register values for '{session._device.name}'."
            )

        return info

    async def _request_writing_session(
        self, session: "_BleMicronovaSession", payload: dict[str, Any]
    ) -> None:
        """Write raw register values through an authenticated session."""
        buffer_ids = await session.get_buffer_ids()
        if buffer_ids:
            # Prime the local session the same way the vendor app does:
            # it reads buffers before sending writes.
            await session.get_buffer_reading(buffer_ids[0])
        response = await session.exchange(self._make_enveloped_command(payload))
        response_payload = response.get("pl", {})
        if response_payload.get("NackErrCode") is not None:
            raise AguaIOTError(
                f"Bluetooth write failed for '{session._device.name}' with NackErrCode={response_payload['NackErrCode']}"
            )

    async def _run_authenticated_session(
        self,
        device: Device,
        action: str,
        operation,
    ) -> Any:
        """Run one BLE action with a single retry on lost authorization."""
        for attempt in range(2):
            try:
                async with self._device_session(device) as session:
                    await session.identity()
                    return await operation(session)
            except (BleakError, AguaIOTConnectionError) as err:
                if not _is_ble_authorization_error(err):
                    raise

                if attempt == 0:
                    _LOGGER.warning(
                        "Micronova BLE link for '%s' lost authorization while %s; retrying once with a fresh connection.",
                        device.name,
                        action,
                    )
                    await asyncio.sleep(0.5)
                    continue

                raise AguaIOTConnectionError(
                    f"Bluetooth connection to '{device.name}' lost authorization while {action}. "
                    "The Navel/T009 module or Bluetooth proxy dropped its authorized GATT state; "
                    "reloading the integration or resetting the BLE module may be required."
                ) from err

    def _device_identity_id(self, device: Device) -> str:
        """Return the device id used by the local BLE protocol."""
        value = _normalize_identity_id(device.ble_mac) or _normalize_identity_id(
            device.product_serial
        )
        if not value:
            raise AguaIOTError(
                f"Missing BLE identity for '{device.name}'. Re-bootstrap the device from the cloud API."
            )
        return value

    def _device_ble_address(self, device: Device) -> str:
        """Return the BLE address to connect to."""
        value = _normalize_ble_address(device.ble_mac)
        if not value:
            raise AguaIOTError(
                f"Missing BLE address for '{device.name}'. Re-bootstrap the device from the cloud API."
            )
        return value

    def _device_security_code(self, device: Device) -> str:
        """Return the BLE security code."""
        value = device.ble_security_code
        if not value:
            raise AguaIOTError(
                f"Missing BLE security code for '{device.name}'. Re-bootstrap the device from the cloud API."
            )
        return str(value)

    def _expected_local_name(self, device: Device) -> str | None:
        """Return the expected T009 local name for the stove."""
        identity = _normalize_identity_id(device.ble_mac)
        if not identity or len(identity) < 6:
            return None

        return f"{DEFAULT_NAME_PREFIX}{identity[-6:]}"

    def _candidate_ble_addresses(self, device: Device) -> list[str]:
        """Return likely BLE addresses for the T009 module.

        The cloud API exposes the base module MAC, while BLE advertisements on real
        devices are often seen on adjacent addresses (for example `+2`).
        """
        address = self._device_ble_address(device)
        candidates = [address]

        for delta in (1, 2, 3):
            candidate = _increment_ble_address(address, delta)
            if candidate not in candidates:
                candidates.append(candidate)

        return candidates

    def _make_enveloped_command(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Wrap a Micronova local payload in the JSON envelope used by the app."""
        return {
            "mt": "Q",
            "s": {"ss": "Apk", "sj": self._session_uuid},
            "r": {"rj": "Navel"},
            "pl": payload,
        }

    def _make_identity_command(self, device: Device) -> dict[str, Any]:
        """Build the local BLE identity command."""
        return self._make_enveloped_command(
            {
                "Id": self._device_identity_id(device),
                "Security": self._device_security_code(device),
                "Cmd": "Identity",
            }
        )

    def _find_ble_device(self, device: Device) -> tuple[Any | None, str]:
        """Find the target BLEDevice in Home Assistant's shared scanner."""
        address = self._device_ble_address(device)
        candidate_addresses = self._candidate_ble_addresses(device)
        expected_name = self._expected_local_name(device)
        scanner_count = bluetooth.async_scanner_count(self.hass, connectable=True)

        if scanner_count == 0:
            return (
                None,
                "No connectable Bluetooth adapters or ESPHome Bluetooth proxies are "
                f"available in Home Assistant for '{device.name}'",
            )

        for connectable in (True, False):
            for candidate_address in candidate_addresses:
                ble_device = bluetooth.async_ble_device_from_address(
                    self.hass,
                    candidate_address,
                    connectable=connectable,
                )
                if ble_device is not None:
                    _LOGGER.debug(
                        "Using BLEDevice for '%s' via address %s (connectable=%s): %s",
                        device.name,
                        candidate_address,
                        connectable,
                        ble_device,
                    )
                    return ble_device, ""

            fallback_prefix_device = None
            for service_info in bluetooth.async_discovered_service_info(
                self.hass, connectable=connectable
            ):
                service_address = service_info.address.upper()
                service_name = (
                    getattr(service_info, "name", None)
                    or getattr(service_info.device, "name", None)
                    or getattr(service_info.advertisement, "local_name", None)
                    or ""
                )

                if service_address in candidate_addresses:
                    _LOGGER.debug(
                        "Matched BLE service info for '%s' by address %s (connectable=%s, name=%s)",
                        device.name,
                        service_address,
                        connectable,
                        service_name,
                    )
                    return service_info.device, ""

                if expected_name and service_name == expected_name:
                    _LOGGER.debug(
                        "Matched BLE service info for '%s' by exact name %s (address=%s, connectable=%s)",
                        device.name,
                        expected_name,
                        service_address,
                        connectable,
                    )
                    return service_info.device, ""

                if fallback_prefix_device is None and service_name.startswith(
                    DEFAULT_NAME_PREFIX
                ):
                    fallback_prefix_device = service_info.device

            if fallback_prefix_device is not None:
                _LOGGER.debug(
                    "Using fallback T009 BLE service info for '%s' (connectable=%s): %s",
                    device.name,
                    connectable,
                    fallback_prefix_device,
                )
                return fallback_prefix_device, ""

        return (
            None,
            f"Micronova BLE device for '{device.name}' was not discovered by Home "
            f"Assistant yet (address={address}, candidates={candidate_addresses}, "
            f"expected_name={expected_name})",
        )

    async def _async_get_ble_device(self, device: Device) -> Any:
        """Resolve the target BLEDevice from Home Assistant's shared scanner."""
        loop = asyncio.get_running_loop()
        wait_seconds = min(max(self.buffer_read_timeout, 10), BLE_DISCOVERY_MAX_WAIT)
        deadline = loop.time() + wait_seconds
        logged_wait = False
        last_reason = ""

        while True:
            ble_device, reason = self._find_ble_device(device)
            if ble_device is not None:
                return ble_device

            last_reason = reason
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise AguaIOTConnectionError(
                    f"{last_reason}. Home Assistant will retry once Bluetooth is ready."
                )

            if not logged_wait:
                _LOGGER.info(
                    "%s; waiting up to %s seconds before failing this update.",
                    last_reason,
                    int(wait_seconds),
                )
                logged_wait = True

            await asyncio.sleep(min(BLE_DISCOVERY_RETRY_INTERVAL, remaining))

    def _device_session(self, device: Device) -> "_BleMicronovaSession":
        """Create a BLE session wrapper for one device."""
        return _BleMicronovaSession(self, device)


class _BleMicronovaSession:
    """Single BLE session used for one read/write sequence."""

    def __init__(self, transport: LocalBleAguaIOT, device: Device) -> None:
        self._transport = transport
        self._device = device
        self._client: BleakClient | None = None
        self._characteristic_uuid: str | None = None
        self._response_ready = asyncio.Event()
        self._notif_len: int | None = None
        self._resolved_target: Any = None

    async def __aenter__(self) -> "_BleMicronovaSession":
        await self._transport._command_lock.acquire()

        try:
            ble_device = await self._transport._async_get_ble_device(self._device)
            self._resolved_target = ble_device
            self._client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                self._device.name,
                max_attempts=3,
            )
            characteristic_uuid = self._resolve_characteristic_uuid()
            self._characteristic_uuid = characteristic_uuid
            await self._client.start_notify(characteristic_uuid, self._handle_notify)
        except AguaIOTConnectionError:
            await self._cleanup_failed_enter()
            raise
        except BleakError as err:
            await self._cleanup_failed_enter()
            raise AguaIOTConnectionError(
                f"Bluetooth connection to '{self._device.name}' failed: {err}"
            ) from err
        except Exception as err:  # noqa: BLE001
            await self._cleanup_failed_enter()
            raise AguaIOTConnectionError(
                f"Bluetooth connection to '{self._device.name}' failed: {err}"
            ) from err

        return self

    async def _cleanup_failed_enter(self) -> None:
        """Disconnect and release the command lock after a failed enter."""
        try:
            if self._client:
                await self._client.disconnect()
        finally:
            self._transport._command_lock.release()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if self._client and self._characteristic_uuid:
                await self._client.stop_notify(self._characteristic_uuid)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Ignoring BLE stop_notify failure: %s", err)
        finally:
            try:
                if self._client:
                    await self._client.disconnect()
            finally:
                self._transport._command_lock.release()

    @property
    def connected_address(self) -> str | None:
        """Return the resolved BLE address for the session."""
        if self._client and getattr(self._client, "address", None):
            return str(self._client.address).upper()

        if isinstance(self._resolved_target, str):
            return self._resolved_target.upper()

        if self._resolved_target is not None and getattr(
            self._resolved_target, "address", None
        ):
            return str(self._resolved_target.address).upper()

        return None

    @property
    def connected_name(self) -> str | None:
        """Return the resolved BLE local name for the session."""
        if self._resolved_target is None:
            return None

        if isinstance(self._resolved_target, str):
            return None

        name = getattr(self._resolved_target, "name", None)
        return str(name) if name else None

    def _resolve_characteristic_uuid(self) -> str:
        """Pick the characteristic used as the JSON tunnel."""
        assert self._client is not None
        preferred = None
        fallback = None

        for service in self._client.services:
            for characteristic in service.characteristics:
                properties = {str(prop).lower() for prop in characteristic.properties}
                if (
                    service.uuid.lower() == self._transport.service_uuid
                    and characteristic.uuid.lower() == self._transport.char_uuid
                ):
                    return characteristic.uuid

                if {"write", "read"} <= properties and (
                    "notify" in properties or "indicate" in properties
                ):
                    preferred = preferred or characteristic.uuid
                elif "write" in properties and (
                    "notify" in properties or "indicate" in properties
                ):
                    fallback = fallback or characteristic.uuid

        if preferred:
            return preferred
        if fallback:
            return fallback

        raise AguaIOTConnectionError(
            f"Could not find a suitable Micronova GATT characteristic on '{self._device.name}'."
        )

    def _handle_notify(self, _sender: Any, data: bytearray) -> None:
        """Process the 2-byte 'response length ready' notification."""
        self._notif_len = int.from_bytes(data[:2], "little") if len(data) >= 2 else None
        self._response_ready.set()

    async def identity(self) -> dict[str, Any]:
        """Authenticate the BLE session."""
        response = await self.exchange(
            self._transport._make_identity_command(self._device)
        )
        payload = response.get("pl", {})
        if payload.get("NackErrCode") is not None:
            raise AguaIOTError(
                f"Bluetooth identity failed for '{self._device.name}' with NackErrCode={payload['NackErrCode']}"
            )
        return response

    async def get_buffer_ids(self) -> list[int]:
        """Return the list of available buffer ids."""
        response = await self.exchange(
            self._transport._make_enveloped_command({"Cmd": "GetBufferId"})
        )
        payload = response.get("pl", {})
        indexes = payload.get("Indexes") or payload.get("indexes") or []
        if isinstance(indexes, list):
            return [int(idx) for idx in indexes]
        return []

    async def get_buffer_reading(self, buffer_id: int) -> dict[str, Any]:
        """Read one Micronova buffer through BLE."""
        return await self.exchange(
            self._transport._make_enveloped_command(
                {"Cmd": "GetBufferReading", "BufferId": int(buffer_id)}
            )
        )

    async def exchange(self, command: dict[str, Any]) -> dict[str, Any]:
        """Send one JSON command and return its JSON response."""
        await self._write_json_message(command)
        expected_len = None
        cmd_name = command.get("pl", {}).get("Cmd")
        notify_timeout = min(self._transport.buffer_read_timeout, 5)
        try:
            await asyncio.wait_for(
                self._response_ready.wait(),
                timeout=notify_timeout,
            )
            expected_len = self._notif_len
        except asyncio.TimeoutError as err:
            _LOGGER.debug(
                "No BLE notification received for '%s' command '%s'; "
                "falling back to direct characteristic read.",
                self._device.name,
                cmd_name,
            )
            if cmd_name != "RequestWriting":
                raise AguaIOTUpdateError(
                    f"Bluetooth response timeout while talking to '{self._device.name}'."
                ) from err

        response = await self._read_json_response(expected_len)
        self._response_ready.clear()
        self._notif_len = None
        return response

    async def _write_json_message(self, obj: dict[str, Any]) -> None:
        """Send the Micronova binary header, then the JSON body."""
        assert self._client is not None
        assert self._characteristic_uuid is not None

        body = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        header = b"JSON" + struct.pack("<H", len(body)) + b"\xf9\x01"

        self._response_ready.clear()
        self._notif_len = None

        await self._client.write_gatt_char(
            self._characteristic_uuid, header, response=True
        )

        mtu = getattr(self._client, "mtu_size", 23) or 23
        chunk_size = max(20, mtu - 3)
        for index in range(0, len(body), chunk_size):
            chunk = body[index : index + chunk_size]
            await self._client.write_gatt_char(
                self._characteristic_uuid,
                chunk,
                response=True,
            )

    async def _read_json_response(self, expected_len: int | None) -> dict[str, Any]:
        """Read one or more chunks from the characteristic until the JSON body is complete."""
        assert self._client is not None
        assert self._characteristic_uuid is not None

        if not expected_len or expected_len <= 0:
            raw = await self._client.read_gatt_char(self._characteristic_uuid)
            return _parse_json_response(bytes(raw))

        data = bytearray()
        last_chunk: bytes | None = None

        for _ in range(32):
            chunk = bytes(await self._client.read_gatt_char(self._characteristic_uuid))
            if not chunk:
                break
            if chunk == last_chunk:
                break
            data.extend(chunk)
            last_chunk = chunk
            if len(data) >= expected_len:
                break

        if not data:
            raise AguaIOTUpdateError(
                f"Bluetooth read returned no data for '{self._device.name}'."
            )

        return _parse_json_response(bytes(data[:expected_len]))


def _parse_json_response(raw: bytes) -> dict[str, Any]:
    """Parse a BLE response that may optionally include the Micronova JSON header."""
    if raw.startswith(b"JSON") and len(raw) >= 8:
        body_len = struct.unpack_from("<H", raw, 4)[0]
        raw = raw[8 : 8 + body_len]

    first_json = raw.find(b"{")
    if first_json != -1:
        raw = raw[first_json:]

    try:
        return json.loads(raw.decode("utf-8", errors="ignore"))
    except json.JSONDecodeError as err:
        raise AguaIOTUpdateError(
            f"Invalid JSON received from the Micronova BLE transport: {raw[:80]!r}"
        ) from err
