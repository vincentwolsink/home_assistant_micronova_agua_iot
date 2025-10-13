"""Support for Micronova Agua IOT heating devices."""

import logging
from datetime import timedelta
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.httpx_client import get_async_client

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP

from .aguaiot import (
    ConnectionError,
    AguaIOTError,
    UnauthorizedError,
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
    DOMAIN,
    PLATFORMS,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the AguaIOT integration."""
    if DOMAIN in config:
        for entry_config in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry_config
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AguaIOT entry."""
    api_url = entry.data[CONF_API_URL]
    customer_code = entry.data[CONF_CUSTOMER_CODE]
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    gen_uuid = entry.data[CONF_UUID]
    login_api_url = entry.data.get(CONF_LOGIN_API_URL)
    brand_id = entry.data.get(CONF_BRAND_ID)
    brand = entry.data.get(CONF_BRAND)
    air_temp_fix = entry.options.get("air_temp_fix", False)
    reading_error_fix = entry.options.get("reading_error_fix", False)
    language = entry.options.get(CONF_LANGUAGE)

    agua = aguaiot(
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
    )

    try:
        await agua.connect()
    except UnauthorizedError as e:
        _LOGGER.error("Agua IOT Unauthorized: %s", e)
        return False
    except ConnectionError as e:
        _LOGGER.error("Connection error to Agua IOT: %s", e)
        return False
    except AguaIOTError as e:
        _LOGGER.error("Unknown Agua IOT error: %s", e)
        return False

    async def async_update_data():
        """Get the latest data."""
        try:
            await agua.update()
        except UnauthorizedError as e:
            _LOGGER.error("Agua IOT Unauthorized: %s", e)
            return False
        except ConnectionError as e:
            _LOGGER.error("Connection error to Agua IOT: %s", e)
            return False
        except AguaIOTError as e:
            _LOGGER.error("Unknown Agua IOT error: %s", e)
            return False

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="aguaiot",
        update_method=async_update_data,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "agua": agua,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Services
    async def async_close_connection(event: Event) -> None:
        """Close AguaIOT connection on HA Stop."""
        # await agua.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
