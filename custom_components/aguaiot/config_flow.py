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
    CONF_BRAND_ID,
    CONF_API_LOGIN_APPLICATION_VERSION,
    CONF_CUSTOMER_CODE,
    CONF_LOGIN_API_URL,
    CONF_UUID,
    DOMAIN,
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
        host_server = user_input[CONF_API_URL]
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

            api_url = user_input[CONF_API_URL]
            customer_code = user_input[CONF_CUSTOMER_CODE]
            brand_id = user_input[CONF_BRAND_ID]
            login_api_url = (
                user_input.get(CONF_LOGIN_API_URL)
                if user_input.get(CONF_LOGIN_API_URL) != ""
                else None
            )
            api_login_application_version = user_input.get(
                CONF_API_LOGIN_APPLICATION_VERSION
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
                    brand_id,
                    api_login_application_version,
                )
                await agua.connect()
            except UnauthorizedError:
                errors["base"] = "unauthorized"
            except ConnectionError:
                errors["base"] = "connection_error"
            except AguaIOTError:
                errors["base"] = "unknown_error"

            if "base" not in errors:
                return self.async_create_entry(
                    title=DOMAIN,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_UUID: gen_uuid,
                        CONF_API_URL: api_url,
                        CONF_CUSTOMER_CODE: customer_code,
                        CONF_BRAND_ID: brand_id,
                        CONF_LOGIN_API_URL: login_api_url,
                        CONF_API_LOGIN_APPLICATION_VERSION: api_login_application_version,
                    },
                )
        else:
            user_input = {}

        data_schema = OrderedDict()
        data_schema[
            vol.Required(CONF_API_URL, default=user_input.get(CONF_API_URL))
        ] = str
        data_schema[
            vol.Optional(
                CONF_LOGIN_API_URL, default=user_input.get(CONF_LOGIN_API_URL, "")
            )
        ] = str
        data_schema[
            vol.Required(CONF_CUSTOMER_CODE, default=user_input.get(CONF_CUSTOMER_CODE))
        ] = str
        data_schema[vol.Required(CONF_BRAND_ID, default="1")] = str
        data_schema[
            vol.Required(CONF_API_LOGIN_APPLICATION_VERSION, default="1.9.5")
        ] = str
        data_schema[vol.Required(CONF_EMAIL, default=user_input.get(CONF_EMAIL))] = str
        data_schema[
            vol.Required(CONF_PASSWORD, default=user_input.get(CONF_PASSWORD))
        ] = str

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors
        )
