"""Update coordinator"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .aguaiot import (
    AguaIOTConnectionError,
    AguaIOTError,
    AguaIOTUnauthorized,
    AguaIOTUpdateError,
    aguaiot,
)
from .const import (
    CONF_AIR_TEMP_FIX,
    CONF_API_URL,
    CONF_BLE_BOOTSTRAP_DEVICES,
    CONF_BLE_CHAR_UUID,
    CONF_BLE_SERVICE_UUID,
    CONF_BRAND,
    CONF_BRAND_ID,
    CONF_BUFFER_READ_TIMEOUT,
    CONF_CONNECTION_MODE,
    CONF_CUSTOMER_CODE,
    CONF_DEVICE_FIXES,
    CONF_FAILURE_THRESHOLD,
    CONF_HTTP_TIMEOUT,
    CONF_LANGUAGE,
    CONF_LOGIN_API_URL,
    CONF_MQTT_SETTINGS,
    CONF_UPDATE_INTERVAL,
    CONF_UUID,
    CONNECTION_MODE_BLUETOOTH,
    CONNECTION_MODE_CLOUD,
    CONNECTION_MODE_LOCAL_MQTT,
    DEFAULT_FAILURE_THRESHOLD,
    DOMAIN,
)
from .eeprom import eeprom_daily_writes_for_device
from .fixture import create_fixture_client
from .local_ble import DEFAULT_CHAR_UUID, DEFAULT_SERVICE_UUID, LocalBleAguaIOT
from .local_mqtt import LocalMqttAguaIOT

_LOGGER = logging.getLogger(__name__)


class AguaIOTDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        update_interval = config_entry.options.get(CONF_UPDATE_INTERVAL, 60)
        failure_threshold = config_entry.options.get(
            CONF_FAILURE_THRESHOLD, DEFAULT_FAILURE_THRESHOLD
        )
        try:
            failure_threshold = int(failure_threshold)
        except (TypeError, ValueError):
            failure_threshold = DEFAULT_FAILURE_THRESHOLD
        self._failure_threshold = max(1, failure_threshold)
        self._consecutive_update_failures = 0
        self._initial_update_completed = False

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
            config_entry=config_entry,
        )

        """Set up AguaIOT entry."""
        api_url = config_entry.data[CONF_API_URL]
        customer_code = config_entry.data[CONF_CUSTOMER_CODE]
        email = config_entry.data[CONF_EMAIL]
        password = config_entry.data[CONF_PASSWORD]
        gen_uuid = config_entry.data[CONF_UUID]
        login_api_url = config_entry.data.get(CONF_LOGIN_API_URL)
        brand_id = config_entry.data.get(CONF_BRAND_ID)
        brand = config_entry.data.get(CONF_BRAND)
        # Device fixes are stored in the device_fixes section, legacy entries
        # stored them flat.
        device_fixes = config_entry.options.get(CONF_DEVICE_FIXES) or {}
        air_temp_fix = device_fixes.get(
            CONF_AIR_TEMP_FIX, config_entry.options.get(CONF_AIR_TEMP_FIX, False)
        )
        language = config_entry.options.get(CONF_LANGUAGE)
        http_timeout = config_entry.options.get(CONF_HTTP_TIMEOUT, 30)
        buffer_read_timeout = config_entry.options.get(CONF_BUFFER_READ_TIMEOUT, 30)
        connection_mode = config_entry.options.get(
            CONF_CONNECTION_MODE, CONNECTION_MODE_CLOUD
        )

        client_kwargs = {
            "api_url": api_url,
            "customer_code": customer_code,
            "email": email,
            "password": password,
            "unique_id": gen_uuid,
            "login_api_url": login_api_url,
            "brand_id": brand_id,
            "brand": brand,
            "async_client": get_async_client(hass),
            "air_temp_fix": air_temp_fix,
            "language": language,
            "http_timeout": http_timeout,
            "buffer_read_timeout": buffer_read_timeout,
            "eeprom_limits": {
                key: config_entry.options[key]
                for key in ("max_eeprom_writes_per_day",)
                if key in config_entry.options
            },
        }

        self._cloud_cache_saved = False
        self.eeprom_writes_per_day: dict[str, int | None] = {}
        mqtt_settings = config_entry.options.get(CONF_MQTT_SETTINGS, {})

        if (fixture_client := create_fixture_client(**client_kwargs)) is not None:
            self.agua = fixture_client
        elif connection_mode == CONNECTION_MODE_BLUETOOTH:
            self.agua = LocalBleAguaIOT(
                hass=hass,
                cached_devices=config_entry.data.get(CONF_BLE_BOOTSTRAP_DEVICES),
                service_uuid=config_entry.options.get(
                    CONF_BLE_SERVICE_UUID, DEFAULT_SERVICE_UUID
                ),
                char_uuid=config_entry.options.get(
                    CONF_BLE_CHAR_UUID, DEFAULT_CHAR_UUID
                ),
                **client_kwargs,
            )
        elif connection_mode == CONNECTION_MODE_LOCAL_MQTT:
            self.agua = LocalMqttAguaIOT(
                hass=hass,
                mqtt_settings=mqtt_settings,
                cached_devices=config_entry.data.get(CONF_BLE_BOOTSTRAP_DEVICES),
                **client_kwargs,
            )
        else:
            self.agua = aguaiot(**client_kwargs, hass=hass)

    @property
    def connection_mode(self) -> str:
        """Return the active connection mode."""
        return self.config_entry.options.get(
            CONF_CONNECTION_MODE, CONNECTION_MODE_CLOUD
        )

    async def _async_setup(self) -> None:
        """Connect to the AguaIOT platform"""
        try:
            await self.agua.connect()
            await self._async_persist_ble_bootstrap_if_needed()
        except AguaIOTUpdateError as e:
            # Raising here makes Home Assistant retry the setup of this config
            # entry instead of setting up the platforms without any data.
            raise UpdateFailed(f"Agua IOT Update error: {e}") from e
        except AguaIOTUnauthorized as e:
            raise UpdateFailed(f"Agua IOT Unauthorized: {e}") from e
        except AguaIOTConnectionError as e:
            raise UpdateFailed(f"Agua IOT Connection error: {e}") from e
        except AguaIOTError as e:
            raise UpdateFailed(f"Agua IOT error: {e}") from e

    async def _async_update_data(self) -> None:
        """Get the latest data."""
        try:
            await self.agua.update()
        except AguaIOTUpdateError as e:
            self._handle_update_failure(f"Agua IOT Update error: {e}", e)
            return
        except AguaIOTUnauthorized as e:
            self._handle_update_failure(f"Agua IOT Unauthorized: {e}", e)
            return
        except AguaIOTConnectionError as e:
            self._handle_update_failure(f"Agua IOT Connection error: {e}", e)
            return
        except AguaIOTError as e:
            self._handle_update_failure(f"Agua IOT error: {e}", e)
            return

        self._consecutive_update_failures = 0
        self._initial_update_completed = True
        await self._async_persist_ble_bootstrap_if_needed()
        await self._async_update_eeprom_usage()

    def _handle_update_failure(self, message: str, error: AguaIOTError) -> None:
        """Keep the last known values until too many consecutive reads fail.

        During the first refresh the failure is always raised, so Home Assistant
        retries the setup of this config entry and entities are only added once
        the devices have been read successfully.
        """
        self._consecutive_update_failures += 1
        if (
            not self._initial_update_completed
            or self._consecutive_update_failures >= self._failure_threshold
        ):
            raise UpdateFailed(message) from error

        _LOGGER.warning(
            "Failed to update %s (%s/%s consecutive failures); "
            "keeping the last known values.",
            self.name,
            self._consecutive_update_failures,
            self._failure_threshold,
        )

    async def _async_update_eeprom_usage(self) -> None:
        """Collect the EEPROM write counts for every stove."""
        usage: dict[str, int | None] = {}
        for device in self.agua.devices:
            try:
                usage[str(device.id_device)] = await eeprom_daily_writes_for_device(
                    self.hass, device, explicit_mac=device.wifi_mac
                )
            except AguaIOTError:
                usage[str(device.id_device)] = None
        self.eeprom_writes_per_day = usage

    async def _async_persist_ble_bootstrap_if_needed(self) -> None:
        """Persist bootstrap data when it is freshly learned from the cloud."""
        # Cache the first complete cloud mapping for subsequent local connections.
        if self.connection_mode == CONNECTION_MODE_CLOUD:
            if self._cloud_cache_saved:
                return
            devices = [device.export_cache() for device in self.agua.devices]
            if (
                devices
                and all(device.get("register_map") for device in devices)
                and devices != self.config_entry.data.get(CONF_BLE_BOOTSTRAP_DEVICES)
            ):
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        CONF_BLE_BOOTSTRAP_DEVICES: devices,
                    },
                )
            self._cloud_cache_saved = bool(devices) and all(
                device.get("register_map") for device in devices
            )
            return

        if not hasattr(self.agua, "cache_dirty") or not self.agua.cache_dirty:
            return

        updated_data = {
            **self.config_entry.data,
            CONF_BLE_BOOTSTRAP_DEVICES: self.agua.export_bootstrap_cache(),
        }
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=updated_data,
        )
        self.agua.mark_cache_persisted()
