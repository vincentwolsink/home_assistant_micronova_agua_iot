"""Support for Agua IOT heating devices."""
import logging

from py_agua_iot import (
    ConnectionError,
    Error as AguaIOTError,
    UnauthorizedError,
    agua_iot,
)

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    TEMP_CELSIUS,
)

from .const import (
    ATTR_DEVICE_ALARM,
    ATTR_DEVICE_STATUS,
    ATTR_HUMAN_DEVICE_STATUS,
    ATTR_REAL_POWER,
    ATTR_SMOKE_TEMP,
    DOMAIN,
    AGUA_STATUS_CLEANING,
    AGUA_STATUS_CLEANING_FINAL,
    AGUA_STATUS_FLAME,
    AGUA_STATUS_OFF,
    AGUA_STATUS_ON,
    CURRENT_HVAC_MAP_AGUA_HEAT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Agua IOT climate, nothing to do."""


async def async_setup_entry(hass, entry, async_add_entities):
    agua: agua_iot = hass.data[DOMAIN][entry.unique_id]
    async_add_entities([AguaIOTHeatingDevice(device) for device in agua.devices], True)
    return True


class AguaIOTHeatingDevice(ClimateEntity):
    """Representation of an Agua IOT heating device."""

    def __init__(self, device):
        """Initialize the thermostat."""
        self._device = device

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            ATTR_DEVICE_ALARM: self._device.alarms,
            ATTR_DEVICE_STATUS: self._device.status,
            ATTR_HUMAN_DEVICE_STATUS: self._device.status_translated,
            ATTR_SMOKE_TEMP: self._device.gas_temperature,
            ATTR_REAL_POWER: self._device.real_power,
        }

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._device.id_device

    @property
    def name(self):
        """Return the name of the device, if any."""
        return self._device.name

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Micronova",
            "model": self._device.name_product,
        }

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_HALVES

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return PRECISION_HALVES

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def min_temp(self):
        """Return the minimum temperature to set."""
        return self._device.min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature to set."""
        return self._device.max_temp

    @property
    def current_temperature(self):
        """Return the current temperature."""
        temp = self._device.air_temperature
        if temp is None:
            temp = self._device.water_temperature
        return temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        set_temp = self._device.set_air_temperature
        if set_temp is None:
            set_temp = self._device.set_water_temperature
        return set_temp

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        if self._device.status not in [0, 6]:
            return HVAC_MODE_HEAT
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def fan_mode(self):
        """Return fan mode."""
        return str(self._device.set_power)

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        fan_modes = []
        for x in range(self._device.min_power, (self._device.max_power + 1)):
            fan_modes.append(str(x))
        return fan_modes

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        if self._device.status_translated in CURRENT_HVAC_MAP_AGUA_HEAT:
            return CURRENT_HVAC_MAP_AGUA_HEAT.get(self._device.status_translated)
        return CURRENT_HVAC_IDLE

    def turn_off(self):
        """Turn device off."""
        try:
            self._device.turn_off()
        except AguaIOTError as err:
            _LOGGER.error("Failed to turn off device, error: %s", err)

    def turn_on(self):
        """Turn device on."""
        try:
            self._device.turn_on()
        except AguaIOTError as err:
            _LOGGER.error("Failed to turn on device, error: %s", err)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        try:
            if self._device.air_temperature is not None:
                self._device.set_air_temperature = temperature
            elif self._device.water_temperature is not None:
                self._device.set_water_temperature = temperature
        except (ValueError, AguaIOTError) as err:
            _LOGGER.error("Failed to set temperature, error: %s", err)

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if fan_mode is None or not fan_mode.isdigit():
            return

        try:
            self._device.set_power = int(fan_mode)
        except AguaIOTError as err:
            _LOGGER.error("Failed to set fan mode, error: %s", err)

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_OFF:
            self.turn_off()
        elif hvac_mode == HVAC_MODE_HEAT:
            self.turn_on()

    def update(self):
        """Get the latest data."""
        try:
            self._device.update()
        except UnauthorizedError:
            _LOGGER.error(
                "Wrong credentials for device %s (%s)",
                self.name,
                self._device.id_device,
            )
            return False
        except ConnectionError:
            _LOGGER.error("Connection to Agua IOT not possible")
            return False
        except AguaIOTError as err:
            _LOGGER.error(
                "Failed to update %s (%s), error: %s",
                self.name,
                self._device.id_device,
                err,
            )
            return False

        return True
