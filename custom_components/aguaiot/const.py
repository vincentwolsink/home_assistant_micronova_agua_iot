"""Agua IOT constants."""

from homeassistant.const import (
    Platform,
    UnitOfTemperature,
    UnitOfPressure,
    REVOLUTIONS_PER_MINUTE,
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
    hybrid_exclude: bool = False
    raw_value: bool = False


@dataclass
class AguaIOTNumberEntityDescription(NumberEntityDescription):
    force_enabled: bool = False
    hybrid_only: bool = False
    hybrid_exclude: bool = False


@dataclass
class AguaIOTCanalizationEntityDescription(ClimateEntityDescription):
    key_temp_set: str | None = None
    key_temp_get: str | None = None
    key_temp2_get: str | None = None
    key_enable: str | None = None
    key2_enable: str | None = None


DOMAIN = "aguaiot"
CONF_API_URL = "api_url"
CONF_CUSTOMER_CODE = "customer_code"
CONF_LOGIN_API_URL = "login_api_url"
CONF_UUID = "uuid"
CONF_ENDPOINT = "endpoint"
CONF_BRAND_ID = "brand_id"
CONF_BRAND = "brand"

AIR_VARIANTS = ["air", "air2", "air_palm"]
WATER_VARIANTS = ["water", "h2o", "h2o_mandata"]

MODE_WOOD = "Wood"
MODE_PELLETS = "Pellet"

STATUS_OFF = ["OFF", "FINAL CLEANING", "STOP", "SHUT OFF", "0", "6"]
STATUS_IDLE = [
    "ECO STOP",
    "STANDBY",
    "STAND BY",
    "STAND-BY",
    "ALARM",
    "MEMORY ALARM",
    "ALARM MEMORY",
    "MEM.ALM",
    "MEM. ALARM",
    "7",
    "8",
    "9",
]

PLATFORMS = [
    Platform.CLIMATE,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
]

UPDATE_INTERVAL = 60

ENDPOINTS = {
    "Alfapalm": {
        CONF_CUSTOMER_CODE: "862148",
        CONF_API_URL: "https://alfaplam.agua-iot.com",
    },
    "APP-O BIOEN": {
        CONF_CUSTOMER_CODE: "289982",
        CONF_API_URL: "https://unical.agua-iot.com",
    },
    "Boreal Home": {
        CONF_CUSTOMER_CODE: "173118",
        CONF_API_URL: "https://boreal.agua-iot.com",
    },
    "Bronpi Home": {
        CONF_CUSTOMER_CODE: "164873",
        CONF_API_URL: "https://bronpi.agua-iot.com",
    },
    "Darwin Evolution": {
        CONF_CUSTOMER_CODE: "475219",
        CONF_API_URL: "https://cola.agua-iot.com",
    },
    "Easy Connect": {
        CONF_CUSTOMER_CODE: "354924",
        CONF_API_URL: "https://remote.mcz.it",
    },
    "Easy Connect Plus": {
        CONF_CUSTOMER_CODE: "746318",
        CONF_API_URL: "https://remote.mcz.it",
    },
    "Easy Connect Poêle": {
        CONF_CUSTOMER_CODE: "354925",
        CONF_API_URL: "https://remote.mcz.it",
    },
    "Elfire Wifi": {
        CONF_CUSTOMER_CODE: "402762",
        CONF_API_URL: "https://elfire.agua-iot.com",
    },
    "EvaCalòr - PuntoFuoco": {
        CONF_CUSTOMER_CODE: "635987",
        CONF_API_URL: "https://evastampaggi.agua-iot.com",
    },
    "Fontana Forni": {
        CONF_CUSTOMER_CODE: "505912",
        CONF_API_URL: "https://fontanaforni.agua-iot.com",
    },
    "Fonte Flamme contrôle 1": {
        CONF_CUSTOMER_CODE: "848324",
        CONF_API_URL: "https://fonteflame.agua-iot.com",
    },
    "Globe-fire": {
        CONF_CUSTOMER_CODE: "634876",
        CONF_API_URL: "https://globefire.agua-iot.com",
    },
    "GO HEAT": {
        CONF_CUSTOMER_CODE: "859435",
        CONF_API_URL: "https://amg.agua-iot.com",
    },
    "Jolly Mec Wi Fi": {
        CONF_CUSTOMER_CODE: "732584",
        CONF_API_URL: "https://jollymec.agua-iot.com",
    },
    "Karmek Wifi": {
        CONF_CUSTOMER_CODE: "403873",
        CONF_API_URL: "https://karmekone.agua-iot.com",
    },
    "Klover Home": {
        CONF_CUSTOMER_CODE: "143789",
        CONF_API_URL: "https://klover.agua-iot.com",
    },
    "LAMINOX Remote Control (2.0)": {
        CONF_CUSTOMER_CODE: "352678",
        CONF_API_URL: "https://laminox.agua-iot.com",
    },
    "Lorflam Home": {
        CONF_CUSTOMER_CODE: "121567",
        CONF_API_URL: "https://lorflam.agua-iot.com",
    },
    "Moretti design": {
        CONF_CUSTOMER_CODE: "624813",
        CONF_API_URL: "https://moretti.agua-iot.com",
    },
    "My Corisit": {
        CONF_CUSTOMER_CODE: "101427",
        CONF_API_URL: "https://mycorisit.agua-iot.com",
    },
    "MyPiazzetta": {
        CONF_CUSTOMER_CODE: "458632",
        CONF_API_URL: "https://piazzetta.agua-iot.com",
        CONF_LOGIN_API_URL: "https://piazzetta-iot.app2cloud.it/api/bridge/endpoint/",
    },
    "MySuperior": {
        CONF_CUSTOMER_CODE: "458632",
        CONF_API_URL: "https://piazzetta.agua-iot.com",
        CONF_LOGIN_API_URL: "https://piazzetta-iot.app2cloud.it/api/bridge/endpoint/",
        CONF_BRAND_ID: "2",
        CONF_BRAND: "superior",
    },
    "Nina": {
        CONF_CUSTOMER_CODE: "999999",
        CONF_API_URL: "https://micronova.agua-iot.com",
    },
    "Nobis-Fi": {
        CONF_CUSTOMER_CODE: "700700",
        CONF_API_URL: "https://nobis.agua-iot.com",
    },
    "Nordic Fire 2.0": {
        CONF_CUSTOMER_CODE: "132678",
        CONF_API_URL: "https://nordicfire.agua-iot.com",
    },
    "Ravelli Wi-Fi": {
        CONF_CUSTOMER_CODE: "953712",
        CONF_API_URL: "https://aico.agua-iot.com",
    },
    "Stufe a pellet Italia": {
        CONF_CUSTOMER_CODE: "015142",
        CONF_API_URL: "https://stufepelletitalia.agua-iot.com",
    },
    "Thermoflux": {
        CONF_CUSTOMER_CODE: "391278",
        CONF_API_URL: "https://thermoflux.agua-iot.com",
    },
    "TS Smart": {
        CONF_CUSTOMER_CODE: "046629",
        CONF_API_URL: "https://timsistem.agua-iot.com",
    },
    "Wi-Phire": {
        CONF_CUSTOMER_CODE: "521228",
        CONF_API_URL: "https://lineavz.agua-iot.com",
    },
}

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
        key="status_get",
        name="Status",
        icon="mdi:fire",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=SensorDeviceClass.ENUM,
    ),
    AguaIOTSensorEntityDescription(
        key="alarms_get",
        name="Alarm",
        icon="mdi:alert-outline",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=SensorDeviceClass.ENUM,
        force_enabled=True,
    ),
    AguaIOTSensorEntityDescription(
        key="real_power_get",
        name="Real Power",
        icon="mdi:gauge",
        native_unit_of_measurement=None,
        state_class=SensorStateClass.MEASUREMENT,
        force_enabled=True,
        raw_value=True,
        hybrid_exclude=True,
    ),
    AguaIOTSensorEntityDescription(
        key="real_power_get",
        name="Real Pellet Power",
        icon="mdi:gauge",
        native_unit_of_measurement=None,
        state_class=SensorStateClass.MEASUREMENT,
        force_enabled=True,
        raw_value=True,
        hybrid_only=True,
    ),
    AguaIOTSensorEntityDescription(
        key="real_power_wood_get",
        name="Real Wood Power",
        icon="mdi:gauge",
        native_unit_of_measurement=None,
        state_class=SensorStateClass.MEASUREMENT,
        force_enabled=True,
        hybrid_only=True,
        raw_value=True,
    ),
    AguaIOTSensorEntityDescription(
        key="vent_front2_get",
        name="Real Vent Front",
        icon="mdi:fan",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=SensorDeviceClass.ENUM,
    ),
    AguaIOTSensorEntityDescription(
        key="vent_rear2_get",
        name="Real Vent Rear",
        icon="mdi:fan",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=SensorDeviceClass.ENUM,
    ),
    AguaIOTSensorEntityDescription(
        key="type_combustible_get",
        name="Fuel",
        icon="mdi:gas-burner",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=SensorDeviceClass.ENUM,
    ),
    AguaIOTSensorEntityDescription(
        key="pres_h2o_get",
        name="Water Pressure",
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    AguaIOTSensorEntityDescription(
        key="pascal_get",
        name="Brazier Pressure",
        native_unit_of_measurement=UnitOfPressure.PA,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    AguaIOTSensorEntityDescription(
        key="giri_estrattore_get",
        name="Extractor Fan",
        icon="mdi:fan",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=None,
    ),
    AguaIOTSensorEntityDescription(
        key="pomp_h2o_get",
        name="Water Pump",
        icon="mdi:pump",
        native_unit_of_measurement=None,
        state_class=None,
        device_class=None,
    ),
    # Temperature sensors
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
        key="temp_air_get",
        name="Air Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AguaIOTSensorEntityDescription(
        key="temp_air2_get",
        name="Air Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AguaIOTSensorEntityDescription(
        key="temp_air_palm_get",
        name="Remote Air Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AguaIOTSensorEntityDescription(
        key="temp_rear2_get",
        name="Vent Rear Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AguaIOTSensorEntityDescription(
        key="temp_front2_get",
        name="Vent Front Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AguaIOTSensorEntityDescription(
        key="temp_water_get",
        name="Water Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AguaIOTSensorEntityDescription(
        key="temp_h2o_mandata_get",
        name="Water Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AguaIOTSensorEntityDescription(
        key="temp_h2o_get",
        name="Water Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
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
    SwitchEntityDescription(
        key="fun_auto_set",
        name="Auto Mode",
        icon="mdi:fan-auto",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key="fun_pwf_set",
        name="Powerful Mode",
        icon="mdi:speedometer",
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
        name="Power",
        icon="mdi:fire",
        native_step=1,
        force_enabled=True,
        hybrid_exclude=True,
    ),
    AguaIOTNumberEntityDescription(
        key="power_set",
        name="Pellet Power",
        icon="mdi:fire",
        native_step=1,
        force_enabled=True,
        hybrid_only=True,
    ),
    AguaIOTNumberEntityDescription(
        key="power_wood_set",
        name="Wood Power",
        icon="mdi:fire",
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
        key=r"canalization_(?P<id>[a-zA-Z0-9]+)_set",
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
        key=r"vent_(?P<id>(front|rear))_set",
        key_enable="vent_{id}2_enable",
        key2_enable="vent_{id}2_enable",
        key_temp_set="temp_{id}_set",
        key_temp_get="temp_{id}_get",
        key_temp2_get="temp_{id}2_get",
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
