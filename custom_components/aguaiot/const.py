"""Agua IOT constants."""
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)

DOMAIN = "aguaiot"

ATTR_DEVICE_ALARM = "alarm_code"
ATTR_DEVICE_STATUS = "device_status"
ATTR_REAL_POWER = "real_power"

CONF_API_URL = "api_url"
CONF_BRAND_ID = "brand_id"
CONF_API_LOGIN_APPLICATION_VERSION = "api_login_application_version"
CONF_CUSTOMER_CODE = "customer_code"
CONF_LOGIN_API_URL = "login_api_url"
CONF_UUID = "uuid"

AGUA_STATUS_CLEANING = "CLEANING FIRE-POT"
AGUA_STATUS_CLEANING_FINAL = "CLEANING FINAL"
AGUA_STATUS_FLAME = "FLAME LIGHT"
AGUA_STATUS_OFF = "OFF"
AGUA_STATUS_ON = "ON"

CURRENT_HVAC_MAP_AGUA_HEAT = {
    AGUA_STATUS_ON: CURRENT_HVAC_HEAT,
    AGUA_STATUS_CLEANING: CURRENT_HVAC_HEAT,
    AGUA_STATUS_CLEANING_FINAL: CURRENT_HVAC_OFF,
    AGUA_STATUS_FLAME: CURRENT_HVAC_HEAT,
    AGUA_STATUS_OFF: CURRENT_HVAC_OFF,
}

DEVICE_TYPE_AIR = "air"
DEVICE_TYPE_WATER = "water"

PLATFORMS = [
    Platform.SENSOR,
    Platform.CLIMATE,
]

UPDATE_INTERVAL = 60

SENSORS = (
    SensorEntityDescription(
        key="gas_temperature",
        name="Smoke Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="status_translated",
        name="Status",
        icon="mdi:fire",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=None,
    ),
)
