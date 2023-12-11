"""Config flow for Agua IOT."""
from collections import OrderedDict
import logging
import uuid

from .aguaiot import (
    ConnectionError,
    AguaIOTError,
    UnauthorizedError,
    aguaiot,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import (
    CONF_API_URL,
    CONF_CUSTOMER_CODE,
    CONF_LOGIN_API_URL,
    CONF_UUID,
    CONF_ENDPOINT,
    DOMAIN,
    ENDPOINTS,
)

_LOGGER = logging.getLogger(__name__)


def conf_entries(hass):
    """Return the email tuples for the domain."""
    return set(
        (entry.data[CONF_EMAIL], entry.data[CONF_API_URL])
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


class AguaIOTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Agua IOT Config Flow handler."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def _entry_in_configuration_exists(self, user_input) -> bool:
        """Return True if config already exists in configuration."""
        email = user_input[CONF_EMAIL]
        host_server = ENDPOINTS[user_input[CONF_ENDPOINT]][CONF_API_URL]
        if (email, host_server) in conf_entries(self.hass):
            return True
        return False

    async def async_step_user(self, user_input=None):
        """User initiated integration."""
        errors = {}
        if user_input is not None:
            # Validate user input
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            endpoint = user_input[CONF_ENDPOINT]
            api_url = ENDPOINTS[endpoint][CONF_API_URL]
            customer_code = ENDPOINTS[endpoint][CONF_CUSTOMER_CODE]
            login_api_url = (
                ENDPOINTS[endpoint][CONF_LOGIN_API_URL]
                if CONF_LOGIN_API_URL in ENDPOINTS[endpoint]
                else None
            )

            if self._entry_in_configuration_exists(user_input):
                return self.async_abort(reason="device_already_configured")

            try:
                gen_uuid = str(uuid.uuid1())
                agua = aguaiot(
                    api_url,
                    customer_code,
                    email,
                    password,
                    gen_uuid,
                    login_api_url,
                )
                await agua.connect()
            except UnauthorizedError as e:
                _LOGGER.error("Agua IOT Unauthorized: %s", e)
                errors["base"] = "unauthorized"
            except ConnectionError as e:
                _LOGGER.error("Connection error to Agua IOT: %s", e)
                errors["base"] = "connection_error"
            except AguaIOTError as e:
                _LOGGER.error("Unknown Agua IOT error: %s", e)
                errors["base"] = "unknown_error"

            if "base" not in errors:
                return self.async_create_entry(
                    title=endpoint,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_UUID: gen_uuid,
                        CONF_API_URL: api_url,
                        CONF_CUSTOMER_CODE: customer_code,
                        CONF_LOGIN_API_URL: login_api_url,
                    },
                )
        else:
            user_input = {}

        data_schema = vol.Schema({
            vol.Required(CONF_ENDPOINT, default=user_input.get(CONF_ENDPOINT)): vol.In(ENDPOINTS.keys()),
            vol.Required(CONF_EMAIL, default=user_input.get(CONF_EMAIL)): str,
            vol.Required(CONF_PASSWORD, default=user_input.get(CONF_PASSWORD)): str
        })
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
