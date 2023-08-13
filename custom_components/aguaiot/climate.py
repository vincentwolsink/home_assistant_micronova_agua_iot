"""Support for Agua IOT heating devices."""
import logging

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVACAction,
    HVACMode,
    ClimateEntityFeature,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from .const import (
    ATTR_DEVICE_ALARM,
    ATTR_DEVICE_STATUS,
    ATTR_REAL_POWER,
    DOMAIN,
    AGUA_STATUS_CLEANING,
    AGUA_STATUS_CLEANING_FINAL,
    AGUA_STATUS_FLAME,
    AGUA_STATUS_OFF,
    AGUA_STATUS_ON,
    CURRENT_HVAC_MAP_AGUA_HEAT,
)
from py_agua_iot import Error as AguaIOTError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.unique_id][
        "coordinator"
    ]
    agua = hass.data[DOMAIN][entry.unique_id]["agua"]
    async_add_entities(
        [AguaIOTHeatingDevice(coordinator, device) for device in agua.devices], True
    )


class AguaIOTHeatingDevice(CoordinatorEntity, ClimateEntity):
    """Representation of an Agua IOT heating device."""

    def __init__(self, coordinator, device):
        """Initialize the thermostat."""
        CoordinatorEntity.__init__(self, coordinator)
        self._device = device

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            ATTR_DEVICE_ALARM: self._device.alarms,
            ATTR_DEVICE_STATUS: self._device.status,
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
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id_device)},
            name=self._device.name,
            manufacturer="Micronova",
            model=self._device.name_product,
        )

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return PRECISION_WHOLE

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def min_temp(self):
        """Return the minimum temperature to set."""
        min_temp = self._device.min_air_temp
        if min_temp is None:
            min_temp = self._device.min_water_temp
        return min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature to set."""
        max_temp = self._device.max_air_temp
        if max_temp is None:
            max_temp = self._device.max_water_temp
        return max_temp

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
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVACMode.HEAT, HVACMode.OFF]

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
        return HVACAction.IDLE

    async def async_turn_off(self):
        """Turn device off."""
        try:
            await self.hass.async_add_executor_job(self._device.turn_off)
            await self.coordinator.async_request_refresh()
        except AguaIOTError as err:
            _LOGGER.error("Failed to turn off device, error: %s", err)

    async def async_turn_on(self):
        """Turn device on."""
        try:
            await self.hass.async_add_executor_job(self._device.turn_on)
            await self.coordinator.async_request_refresh()
        except AguaIOTError as err:
            _LOGGER.error("Failed to turn on device, error: %s", err)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        try:
            if self._device.air_temperature is not None:
                await self.hass.async_add_executor_job(
                    setattr, self._device, "set_air_temperature", temperature
                )
            elif self._device.water_temperature is not None:
                await self.hass.async_add_executor_job(
                    setattr, self._device, "set_water_temperature", temperature
                )
            await self.coordinator.async_request_refresh()
        except (ValueError, AguaIOTError) as err:
            _LOGGER.error("Failed to set temperature, error: %s", err)

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if fan_mode is None or not fan_mode.isdigit():
            return

        try:
            await self.hass.async_add_executor_job(
                setattr, self._device, "set_power", int(fan_mode)
            )
            await self.coordinator.async_request_refresh()
        except AguaIOTError as err:
            _LOGGER.error("Failed to set fan mode, error: %s", err)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()
