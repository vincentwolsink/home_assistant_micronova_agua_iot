"""Support for Micronova Agua IOT heating devices."""
import logging
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP

from py_agua_iot import (
    ConnectionError,
    Error as AguaIOTError,
    UnauthorizedError,
    agua_iot,
)

from .const import (
    CONF_API_URL,
    CONF_BRAND_ID,
    CONF_CUSTOMER_CODE,
    CONF_LOGIN_API_URL,
    CONF_API_LOGIN_APPLICATION_VERSION,
    CONF_UUID,
    DOMAIN,
    PLATFORMS,
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
    brand_id = entry.data[CONF_BRAND_ID]
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    gen_uuid = entry.data[CONF_UUID]
    login_api_url = (
        entry.data.get(CONF_LOGIN_API_URL)
        if entry.data.get(CONF_LOGIN_API_URL) != ""
        else None
    )
    api_login_application_version = (
        entry.data.get(CONF_API_LOGIN_APPLICATION_VERSION)
        if entry.data.get(CONF_API_LOGIN_APPLICATION_VERSION) != ""
        else "1.6.0"
    )

    try:
        debug = _LOGGER.getEffectiveLevel() == logging.DEBUG
        agua = await hass.async_add_executor_job(
            agua_iot,
            api_url,
            customer_code,
            email,
            password,
            gen_uuid,
            login_api_url,
            brand_id,
            debug,
            api_login_application_version,
        )
    except UnauthorizedError:
        _LOGGER.error("Wrong credentials for Agua IOT")
        return False
    except ConnectionError:
        _LOGGER.error("Connection to Agua IOT not possible")
        return False
    except AguaIOTError as err:
        _LOGGER.error("Unknown Agua IOT error: %s", err)
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.unique_id] = agua

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
        agua: agua_iot = hass.data[DOMAIN].pop(entry.unique_id)
        # await agua.close()

    return unload_ok
