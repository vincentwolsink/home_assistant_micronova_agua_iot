"""Agua IOT constants."""
from homeassistant.const import Platform
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
)

DOMAIN = "aguaiot"

ATTR_DEVICE_ALARM = "alarm_code"
ATTR_DEVICE_STATUS = "device_status"
ATTR_HUMAN_DEVICE_STATUS = "human_device_status"
ATTR_REAL_POWER = "real_power"
ATTR_SMOKE_TEMP = "smoke_temperature"

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

PLATFORMS = [
    #Platform.SENSOR,
    Platform.CLIMATE,

]