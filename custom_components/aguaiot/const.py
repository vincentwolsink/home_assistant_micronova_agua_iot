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
    hybrid_only: bool = False
    icon_on: str | None = None


@dataclass
class AguaIOTSensorEntityDescription(SensorEntityDescription):
    force_enabled: bool = False
    hybrid_only: bool = False


@dataclass
class AguaIOTNumberEntityDescription(NumberEntityDescription):
    force_enabled: bool = False
    hybrid_only: bool = False


@dataclass
class AguaIOTCanalizationEntityDescription(ClimateEntityDescription):
    key_temp_set: str | None = None
    key_temp_get: str | None = None


DOMAIN = "aguaiot"
CONF_API_URL = "api_url"
CONF_CUSTOMER_CODE = "customer_code"
CONF_LOGIN_API_URL = "login_api_url"
CONF_UUID = "uuid"

DEVICE_VARIANTS = ["water", "air", "air2", "air_palm"]
MODE_WOOD = "Wood"
MODE_PELLETS = "Pellet"

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
        icon="mdi:fire",
        icon_on="mdi:fire-alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    AguaIOTBinarySensorEntityDescription(
        key="popup_riserva_wood_get",
        name="Wood Reserve",
        icon="mdi:fire",
        icon_on="mdi:fire-alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        force_enabled=True,
    ),
    AguaIOTBinarySensorEntityDescription(
        key="thermostat_contact_get",
        name="External Thermostat",
        icon="mdi:electric-switch",
        icon_on="mdi:electric-switch-closed",
    ),
    AguaIOTBinarySensorEntityDescription(
        key="thermostat_contact_rear_get",
        name="External Thermostat Rear",
        icon="mdi:electric-switch",
        icon_on="mdi:electric-switch-closed",
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
        hybrid_only=True,
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
    AguaIOTNumberEntityDescription(
        key="es_air_start_set",
        name="Energy Saving Start",
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    AguaIOTNumberEntityDescription(
        key="es_air_stop_set",
        name="Energy Saving Stop",
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    AguaIOTNumberEntityDescription(
        key="power_set",
        name="Pellet Power",
        native_step=1,
        hybrid_only=True,
    ),
    AguaIOTNumberEntityDescription(
        key="power_wood_set",
        name="Wood Power",
        native_step=1,
        hybrid_only=True,
    ),
)

CLIMATE_CANALIZATIONS = (
    AguaIOTCanalizationEntityDescription(
        name="Multifire {id}",
        key=r"multifire_(?P<id>\d+)_set",
        icon="mdi:fan",
    ),
    AguaIOTCanalizationEntityDescription(
        name="Canalization {id}",
        key=r"canalization_(?P<id>\d+)_set",
        icon="mdi:fan",
    ),
    AguaIOTCanalizationEntityDescription(
        name="Canalization {id}",
        key=r"canalization_(?P<id>\d+)_vent_set",
        key_temp_set="canalization_{id}_temp_air_set",
        key_temp_get="canalization_{id}_temp_air_get",
        icon="mdi:fan",
    ),
    AguaIOTCanalizationEntityDescription(
        name="Vent {id}",
        key=r"vent_(?P<id>front)_set",
        key_temp_set="temp_{id}_set",
        key_temp_get="temp_{id}_get",
        icon="mdi:fan",
    ),
    # Weird nobis habit of having temp_rear_set and temp_rear2_get
    AguaIOTCanalizationEntityDescription(
        name="Vent {id}",
        key=r"vent_(?P<id>rear)_set",
        key_temp_set="temp_{id}_set",
        key_temp_get="temp_{id}2_get",
        icon="mdi:fan",
    ),
    AguaIOTCanalizationEntityDescription(
        name="Vent {id}",
        key=r"vent_(?!(front|rear))(?P<id>\w+)_set",
        key_temp_set="temp_{id}_set",
        key_temp_get="temp_{id}_get",
        icon="mdi:fan",
    ),
)
