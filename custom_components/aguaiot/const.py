"""Agua IOT constants."""
from homeassistant.const import (
    Platform,
    UnitOfTemperature,
)
from homeassistant.components.climate.const import HVACAction
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
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
from homeassistant.components.climate import (
    ClimateEntityDescription,
)
from dataclasses import dataclass


@dataclass
class AguaIOTBinarySensorEntityDescription(BinarySensorEntityDescription):
    force_enabled: bool = False


@dataclass
class AguaIOTSensorEntityDescription(SensorEntityDescription):
    force_enabled: bool = False


DOMAIN = "aguaiot"
CONF_API_URL = "api_url"
CONF_CUSTOMER_CODE = "customer_code"
CONF_LOGIN_API_URL = "login_api_url"
CONF_UUID = "uuid"

DEVICE_VARIANTS = ["water", "air", "air2", "air_palm"]

PLATFORMS = [
    Platform.CLIMATE,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
]

UPDATE_INTERVAL = 60

BINARY_SENSORS = (
    AguaIOTBinarySensorEntityDescription(
        key="ris_pellet_ris_get",
        name="Pellets Depleted",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    AguaIOTBinarySensorEntityDescription(
        key="popup_riserva_wood_get",
        name="Wood Reserve",
        icon="mdi:fire-alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        force_enabled=True,
    ),
)

SENSORS = (
    AguaIOTSensorEntityDescription(
        key="temp_gas_flue_get",
        name="Smoke Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AguaIOTSensorEntityDescription(
        key="temp_probe_k_get",
        name="Flame Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AguaIOTSensorEntityDescription(
        key="status_get",
        name="Status",
        icon="mdi:fire",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=None,
    ),
    AguaIOTSensorEntityDescription(
        key="alarms_get",
        name="Alarm",
        icon="mdi:alert-outline",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=None,
        force_enabled=True,
    ),
    AguaIOTSensorEntityDescription(
        key="real_power_get",
        name="Real Power",
        icon="mdi:gauge",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=None,
        force_enabled=True,
    ),
    AguaIOTSensorEntityDescription(
        key="real_power_wood_get",
        name="Real Wood Power",
        icon="mdi:gauge",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=None,
        force_enabled=True,
    ),
)

SWITCHES = (
    SwitchEntityDescription(
        key="natural_mode_manual_set",
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
        key="es_air_start_set",
        name="Energy Saving Start",
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    NumberEntityDescription(
        key="es_air_stop_set",
        name="Energy Saving Stop",
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    NumberEntityDescription(
        key="power_set",
        name="Pellet Power",
        native_step=1,
    ),
    NumberEntityDescription(
        key="power_wood_set",
        name="Wood Power",
        native_step=1,
    ),
)

CLIMATE_FANS = (
    ClimateEntityDescription(
        key=r"multifire_\d+_set",
        icon="mdi:fan",
    ),
    ClimateEntityDescription(
        key=r"canalization_\d+_set",
        icon="mdi:fan",
    ),
    ClimateEntityDescription(
        key=r"vent_front_set",
        icon="mdi:fan",
    ),
)

CLIMATE_CANALIZATIONS = (
    ClimateEntityDescription(
        key=r"^(canalization_\d+)_temp_\w+_set",
    ),
)
