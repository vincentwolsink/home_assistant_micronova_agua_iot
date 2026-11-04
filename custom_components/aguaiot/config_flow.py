"""Config flow for Agua IOT."""

import logging
import uuid

import voluptuous as vol
from homeassistant.config_entries import (
    CONN_CLASS_CLOUD_POLL,
    ConfigEntry,
    ConfigFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.helpers.httpx_client import get_async_client

from .aguaiot import (
    AguaIOTConnectionError,
    AguaIOTError,
    AguaIOTUnauthorized,
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
    CONF_ENDPOINT,
    CONF_HTTP_TIMEOUT,
    CONF_LANGUAGE,
    CONF_LOGIN_API_URL,
    CONF_MQTT_SETTINGS,
    CONF_READING_ERROR_FIX,
    CONF_UPDATE_INTERVAL,
    CONF_UUID,
    CONNECTION_MODE_BLUETOOTH,
    CONNECTION_MODE_CLOUD,
    CONNECTION_MODE_LOCAL_MQTT,
    DOMAIN,
    ENDPOINTS,
)
from .eeprom import DEFAULT_DAILY_LIMIT
from .fixture import create_fixture_client
from .local_ble import DEFAULT_CHAR_UUID, DEFAULT_SERVICE_UUID, LocalBleAguaIOT
from .local_mqtt import LocalMqttAguaIOT, LocalMqttSetupError

_LOGGER = logging.getLogger(__name__)


def conf_entries(hass):
    """Return the email tuples for the domain."""
    return {
        (entry.data[CONF_EMAIL], entry.data[CONF_API_URL])
        for entry in hass.config_entries.async_entries(DOMAIN)
    }


class AguaIOTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Agua IOT Config Flow handler."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    def _entry_in_configuration_exists(self, user_input) -> bool:
        """Return True if config already exists in configuration."""
        email = user_input[CONF_EMAIL]
        host_server = ENDPOINTS[user_input[CONF_ENDPOINT]][CONF_API_URL]
        return (email, host_server) in conf_entries(self.hass)

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
            login_api_url = ENDPOINTS[endpoint].get(CONF_LOGIN_API_URL)
            brand_id = ENDPOINTS[endpoint].get(CONF_BRAND_ID)
            brand = ENDPOINTS[endpoint].get(CONF_BRAND)

            if self._entry_in_configuration_exists(user_input):
                return self.async_abort(reason="device_already_configured")

            try:
                gen_uuid = str(uuid.uuid1())
                agua = create_fixture_client() or aguaiot(
                    api_url=api_url,
                    customer_code=customer_code,
                    email=email,
                    password=password,
                    unique_id=gen_uuid,
                    login_api_url=login_api_url,
                    brand_id=brand_id,
                    brand=brand,
                    async_client=get_async_client(self.hass),
                )
                await agua.connect()
            except AguaIOTUnauthorized as e:
                _LOGGER.error("Agua IOT Unauthorized: %s", e)
                errors["base"] = "unauthorized"
            except AguaIOTConnectionError as e:
                _LOGGER.error("Agua IOT Connection error: %s", e)
                errors["base"] = "connection_error"
            except AguaIOTError as e:
                _LOGGER.error("Agua IOT error: %s", e)
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
                        CONF_BRAND_ID: brand_id,
                        CONF_BRAND: brand,
                    },
                )
        else:
            user_input = {}

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENDPOINT, default=user_input.get(CONF_ENDPOINT)
                ): vol.In(ENDPOINTS.keys()),
                vol.Required(CONF_EMAIL, default=user_input.get(CONF_EMAIL)): str,
                vol.Required(CONF_PASSWORD, default=user_input.get(CONF_PASSWORD)): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return AguaIOTOptionsFlowHandler()


class AguaIOTOptionsFlowHandler(OptionsFlowWithReload):
    async def async_step_init(self, _user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    def _build_client(self, connection_mode, user_input=None):
        """Create the configured cloud, BLE, or local MQTT transport."""
        entry = self.config_entry
        options = {**entry.options, **(user_input or {})}
        # Device fixes are stored in the device_fixes section, legacy entries
        # stored them flat.
        device_fixes = options.get(CONF_DEVICE_FIXES) or {}
        return_kwargs = {
            "api_url": entry.data.get(CONF_API_URL),
            "customer_code": entry.data.get(CONF_CUSTOMER_CODE),
            "email": entry.data.get(CONF_EMAIL),
            "password": entry.data.get(CONF_PASSWORD),
            "unique_id": entry.data.get(CONF_UUID),
            "login_api_url": entry.data.get(CONF_LOGIN_API_URL),
            "brand_id": entry.data.get(CONF_BRAND_ID),
            "brand": entry.data.get(CONF_BRAND),
            "async_client": get_async_client(self.hass),
            "air_temp_fix": device_fixes.get(
                CONF_AIR_TEMP_FIX, options.get(CONF_AIR_TEMP_FIX, False)
            ),
            "reading_error_fix": device_fixes.get(
                CONF_READING_ERROR_FIX, options.get(CONF_READING_ERROR_FIX, False)
            ),
            "eeprom_limits": {
                key: options[key]
                for key in ("max_eeprom_writes_per_day",)
                if key in options
            },
            "language": options.get(CONF_LANGUAGE, "ENG"),
            "http_timeout": options.get(CONF_HTTP_TIMEOUT, 30),
            "buffer_read_timeout": options.get(CONF_BUFFER_READ_TIMEOUT, 30),
        }

        if (fixture_client := create_fixture_client(**return_kwargs)) is not None:
            return fixture_client

        if connection_mode == CONNECTION_MODE_BLUETOOTH:
            return LocalBleAguaIOT(
                hass=self.hass,
                cached_devices=entry.data.get(CONF_BLE_BOOTSTRAP_DEVICES),
                service_uuid=options.get(CONF_BLE_SERVICE_UUID, DEFAULT_SERVICE_UUID),
                char_uuid=options.get(CONF_BLE_CHAR_UUID, DEFAULT_CHAR_UUID),
                **return_kwargs,
            )

        if connection_mode == CONNECTION_MODE_LOCAL_MQTT:
            return LocalMqttAguaIOT(
                hass=self.hass,
                mqtt_settings=options.get(CONF_MQTT_SETTINGS, {}),
                cached_devices=entry.data.get(CONF_BLE_BOOTSTRAP_DEVICES),
                **return_kwargs,
            )

        return aguaiot(**return_kwargs)

    def _languages(self):
        """Return the available register description languages."""
        languages = ["ENG"]
        coordinator = getattr(self.config_entry, "runtime_data", None)
        agua = getattr(coordinator, "agua", None)
        if agua and getattr(agua, "devices", None):
            try:
                languages = sorted(
                    agua.devices[0].get_register_value_options_languages(
                        "status_managed_get"
                    )
                )
            except (KeyError, IndexError, AttributeError):
                pass

        # During setup the mapping may have no value options yet. Preserve the
        # configured language so unrelated settings can still be saved.
        return sorted(
            set(languages or ["ENG"])
            | {self.config_entry.options.get(CONF_LANGUAGE, "ENG")}
        )

    def _build_schema(self, user_input=None):
        """Build the options form schema."""
        user_input = user_input or {}
        # Device fixes are stored in the device_fixes section, legacy entries
        # stored them flat. Submitted values take precedence over stored ones.
        submitted_fixes = user_input.get(CONF_DEVICE_FIXES) or {}
        stored_fixes = self.config_entry.options.get(CONF_DEVICE_FIXES) or {}
        air_temp_fix_default = submitted_fixes.get(
            CONF_AIR_TEMP_FIX,
            stored_fixes.get(
                CONF_AIR_TEMP_FIX,
                self.config_entry.options.get(CONF_AIR_TEMP_FIX, False),
            ),
        )
        reading_error_fix_default = submitted_fixes.get(
            CONF_READING_ERROR_FIX,
            stored_fixes.get(
                CONF_READING_ERROR_FIX,
                self.config_entry.options.get(CONF_READING_ERROR_FIX, False),
            ),
        )
        schema = {
            vol.Optional(
                CONF_CONNECTION_MODE,
                default=user_input.get(
                    CONF_CONNECTION_MODE,
                    self.config_entry.options.get(
                        CONF_CONNECTION_MODE, CONNECTION_MODE_CLOUD
                    ),
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        CONNECTION_MODE_CLOUD,
                        CONNECTION_MODE_BLUETOOTH,
                        CONNECTION_MODE_LOCAL_MQTT,
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="connection_mode",
                )
            ),
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=user_input.get(
                    CONF_UPDATE_INTERVAL,
                    self.config_entry.options.get(CONF_UPDATE_INTERVAL, 60),
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=10)),
            vol.Optional(
                CONF_HTTP_TIMEOUT,
                default=user_input.get(
                    CONF_HTTP_TIMEOUT,
                    self.config_entry.options.get(CONF_HTTP_TIMEOUT, 30),
                ),
            ): vol.All(vol.Coerce(int), vol.Range(max=60)),
            vol.Optional(
                CONF_BUFFER_READ_TIMEOUT,
                default=user_input.get(
                    CONF_BUFFER_READ_TIMEOUT,
                    self.config_entry.options.get(CONF_BUFFER_READ_TIMEOUT, 30),
                ),
            ): vol.All(vol.Coerce(int), vol.Range(max=60)),
            vol.Optional(
                "max_eeprom_writes_per_day",
                default=user_input.get(
                    "max_eeprom_writes_per_day",
                    self.config_entry.options.get(
                        "max_eeprom_writes_per_day", DEFAULT_DAILY_LIMIT
                    ),
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(
                CONF_LANGUAGE,
                default=user_input.get(
                    CONF_LANGUAGE,
                    self.config_entry.options.get(CONF_LANGUAGE, "ENG"),
                ),
            ): vol.In(self._languages()),
            CONF_DEVICE_FIXES: section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_AIR_TEMP_FIX,
                            default=air_temp_fix_default,
                        ): bool,
                        vol.Optional(
                            CONF_READING_ERROR_FIX,
                            default=reading_error_fix_default,
                        ): bool,
                    }
                )
            ),
        }
        return vol.Schema(schema)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            submitted_mqtt = CONF_MQTT_SETTINGS in user_input
            user_input = {**self.config_entry.options, **user_input}
            self._pending_options = user_input
            connection_mode = user_input.get(
                CONF_CONNECTION_MODE,
                self.config_entry.options.get(
                    CONF_CONNECTION_MODE, CONNECTION_MODE_CLOUD
                ),
            )
            if connection_mode == CONNECTION_MODE_LOCAL_MQTT and not submitted_mqtt:
                return await self.async_step_mqtt_settings()
            agua = None
            try:
                agua = self._build_client(connection_mode, user_input)
                await agua.connect()
                if connection_mode in (
                    CONNECTION_MODE_BLUETOOTH,
                    CONNECTION_MODE_LOCAL_MQTT,
                ):
                    await agua.validate_local_connection()
            except AguaIOTUnauthorized as e:
                _LOGGER.error("Agua IOT Unauthorized: %s", e)
                errors["base"] = "unauthorized"
            except LocalMqttSetupError as e:
                errors["base"] = e.key
            except AguaIOTConnectionError as e:
                _LOGGER.error("Agua IOT Connection error: %s", e)
                errors["base"] = "connection_error"
            except AguaIOTError as e:
                _LOGGER.error("Agua IOT error: %s", e)
                errors["base"] = "unknown_error"
            else:
                return self.async_create_entry(title="", data=user_input)
            finally:
                if agua and hasattr(agua, "close"):
                    await agua.close()

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_schema(user_input),
            errors=errors,
        )

    async def async_step_mqtt_settings(self, user_input=None):
        options = getattr(self, "_pending_options", self.config_entry.options)
        stored = options.get(CONF_MQTT_SETTINGS, {})
        errors = {}
        if user_input is not None:
            values = {**stored, **user_input}
            values["hostname"] = values.get("hostname", "").strip()
            if not values.get("password") and stored.get("password"):
                values["password"] = stored["password"]
            if not errors:
                return await self.async_step_user(
                    {**options, CONF_MQTT_SETTINGS: values}
                )
        defaults = {**stored, **(user_input or {})}
        return self.async_show_form(
            step_id="mqtt_settings",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Optional("hostname", default=defaults.get("hostname", "")): str,
                    vol.Required("port", default=defaults.get("port", 1883)): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                    vol.Optional("username", default=defaults.get("username", "")): str,
                    vol.Optional(
                        "password", default=defaults.get("password", "")
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
        )
