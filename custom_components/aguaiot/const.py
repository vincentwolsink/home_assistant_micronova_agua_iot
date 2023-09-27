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

from dataclasses import dataclass

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

DEVICE_VARIANTS = ["water", "air", "air2", "air_palm"]

PLATFORMS = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
]

UPDATE_INTERVAL = 60


@dataclass
class AguaIotSensorEntityDescription(SensorEntityDescription):
    enable_key: str | None = None


@dataclass
class AguaIotSwitchEntityDescription(SwitchEntityDescription):
    enable_key: str | None = None


@dataclass
class AguaIotNumberEntityDescription(NumberEntityDescription):
    enable_key: str | None = None


SENSORS = (
    AguaIotSensorEntityDescription(
        key="temp_gas_flue_get",
        name="Smoke Temperature",
        enable_key=None,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AguaIotSensorEntityDescription(
        key="temp_probe_k_get",
        name="Flame Temperature",
        enable_key=None,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AguaIotSensorEntityDescription(
        key="status_get",
        name="Status",
        enable_key=None,
        icon="mdi:fire",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=None,
    ),
    AguaIotSensorEntityDescription(
        key="alarms_get",
        name="Alarm",
        enable_key=None,
        icon="mdi:alert-outline",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=None,
    ),
    AguaIotSensorEntityDescription(
        key="real_power_get",
        name="Real Power",
        enable_key="real_power_enable",
        icon="mdi:gauge",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=None,
    ),
)

SWITCHES = (
    AguaIotSwitchEntityDescription(
        key="natural_mode",
        name="Natural Mode",
        enable_key=None,
        icon="mdi:fan-off",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    AguaIotSwitchEntityDescription(
        key="standby_set",
        name="Standby",
        enable_key=None,
        icon="mdi:power-standby",
        device_class=SwitchDeviceClass.SWITCH,
    ),
)

NUMBERS = (
    AguaIotNumberEntityDescription(
        key="energy_saving_air_start",
        name="Energy Saving Start",
        enable_key=None,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    AguaIotNumberEntityDescription(
        key="energy_saving_air_stop",
        name="Energy Saving Stop",
        enable_key=None,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
)
