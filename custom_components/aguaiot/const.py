"""Agua IOT constants."""
from homeassistant.const import (
    Platform,
    UnitOfTemperature,
)
from homeassistant.components.climate.const import HVACAction
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntityDescription,
)
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
)

DOMAIN = "aguaiot"
CONF_API_URL = "api_url"
CONF_BRAND_ID = "brand_id"
CONF_API_LOGIN_APPLICATION_VERSION = "api_login_application_version"
CONF_CUSTOMER_CODE = "customer_code"
CONF_LOGIN_API_URL = "login_api_url"
CONF_UUID = "uuid"

CURRENT_HVAC_MAP_AGUA_HEAT = {
    "WORK": HVACAction.HEATING,
    "FIRE POT CLEANING": HVACAction.HEATING,
    "FINAL CLEANING": HVACAction.OFF,
    "FLAME LIGHT": HVACAction.HEATING,
    "OFF": HVACAction.OFF,
}

DEVICE_TYPE_AIR = "air"
DEVICE_TYPE_WATER = "water"

PLATFORMS = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
]

UPDATE_INTERVAL = 60

SENSORS = (
    SensorEntityDescription(
        key="temp_gas_flue_get",
        name="Smoke Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="status_get",
        name="Status",
        icon="mdi:fire",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=None,
    ),
    SensorEntityDescription(
        key="alarms_get",
        name="Alarm",
        icon="mdi:alert-outline",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=None,
    ),
    SensorEntityDescription(
        key="real_power_get",
        name="Real Power",
        icon="mdi:gauge",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=None,
    ),
)

SWITCHES = (
    SwitchEntityDescription(
        key="natural_mode",
        name="Natural Mode",
        icon="mdi:fan-off",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key="standby_set",
        name="Standby",
        icon="mdi:power-standby",
        device_class=SwitchDeviceClass.SWITCH,
    ),
)

NUMBERS = (
    NumberEntityDescription(
        key="energy_saving_air_start",
        name="Energy Saving Start",
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    NumberEntityDescription(
        key="energy_saving_air_stop",
        name="Energy Saving Stop",
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
)
