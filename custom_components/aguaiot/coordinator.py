"""Update coordinator"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.httpx_client import get_async_client

from .aguaiot import (
    AguaIOTConnectionError,
    AguaIOTError,
    AguaIOTUnauthorized,
    AguaIOTTimeout,
    aguaiot,
)

from .const import (
    CONF_API_URL,
    CONF_CUSTOMER_CODE,
    CONF_LOGIN_API_URL,
    CONF_UUID,
    CONF_BRAND_ID,
    CONF_BRAND,
    CONF_LANGUAGE,
    CONF_AIR_TEMP_FIX,
    CONF_READING_ERROR_FIX,
    CONF_HTTP_TIMEOUT,
    CONF_BUFFER_READ_TIMEOUT,
    DOMAIN,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class AguaIOTDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
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
        air_temp_fix = config_entry.options.get(CONF_AIR_TEMP_FIX, False)
        reading_error_fix = config_entry.options.get(CONF_READING_ERROR_FIX, False)
        language = config_entry.options.get(CONF_LANGUAGE)
        http_timeout = config_entry.options.get(CONF_HTTP_TIMEOUT)
        buffer_read_timeout = config_entry.options.get(CONF_BUFFER_READ_TIMEOUT)

        self.agua = aguaiot(
            api_url=api_url,
            customer_code=customer_code,
            email=email,
            password=password,
            unique_id=gen_uuid,
            login_api_url=login_api_url,
            brand_id=brand_id,
            brand=brand,
            async_client=get_async_client(hass),
            air_temp_fix=air_temp_fix,
            reading_error_fix=reading_error_fix,
            language=language,
            http_timeout=http_timeout,
            buffer_read_timeout=buffer_read_timeout,
        )

    async def _async_setup(self) -> None:
        """Connect to the AguaIOT platform"""
        try:
            await self.agua.connect()
            await self.agua.update()
        except AguaIOTUnauthorized as e:
            raise UpdateFailed(f"Agua IOT Unauthorized: {e}") from e
        except AguaIOTConnectionError as e:
            raise UpdateFailed(f"Agua IOT Connection error: {e}") from e
        except AguaIOTTimeout as e:
            raise UpdateFailed(f"Agua IOT Timeout: {e}") from e
        except AguaIOTError as e:
            raise UpdateFailed(f"Agua IOT error: {e}") from e

    async def _async_update_data(self) -> None:
        """Get the latest data."""
        try:
            await self.agua.update()
        except AguaIOTUnauthorized as e:
            raise UpdateFailed(f"Agua IOT Unauthorized: {e}") from e
        except AguaIOTConnectionError as e:
            raise UpdateFailed(f"Agua IOT Connection error: {e}") from e
        except AguaIOTTimeout as e:
            raise UpdateFailed(f"Agua IOT Timeout: {e}") from e
        except AguaIOTError as e:
            raise UpdateFailed(f"Agua IOT error: {e}") from e
