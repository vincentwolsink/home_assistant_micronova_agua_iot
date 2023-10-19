"""Support for Agua IOT heating devices."""
import logging
import re

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
    UnitOfTemperature,
    PRECISION_HALVES,
)
from .const import (
    DOMAIN,
    DEVICE_VARIANTS,
)
from .aguaiot import AguaIOTError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    agua = hass.data[DOMAIN][entry.entry_id]["agua"]
    entities = []
    for device in agua.devices:
        entities.append(AguaIOTHeatingDevice(coordinator, device))

        for canalization in list(
            set(
                [
                    m.group(1)
                    for i in device.registers
                    for m in [re.match(r"^(canalization_\d+)_temp_\w+", i.lower())]
                    if m and device.get_register_enabled(m.group(0))
                ]
            )
        ):
            entities.append(
                AguaIOTCanalizationDevice(coordinator, device, canalization)
            )

        for multifan in list(
            set(
                [
                    m.group(1)
                    for i in device.registers
                    for m in [re.match(r"(multifire_\d+)_\w+", i.lower())]
                    if m and device.get_register_enabled(m.group(0))
                ]
            )
        ):
            entities.append(AguaIOTFanDevice(coordinator, device, multifan))

    async_add_entities(entities, True)


class AguaIOTClimateDevice(CoordinatorEntity, ClimateEntity):
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
    def temperature_unit(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_HALVES


class AguaIOTHeatingDevice(AguaIOTClimateDevice):
    """Representation of an Agua IOT heating device."""

    def __init__(self, coordinator, device):
        """Initialize the thermostat."""
        CoordinatorEntity.__init__(self, coordinator)
        self._device = device

        self._temperature_get_key = None
        for variant in DEVICE_VARIANTS:
            if (
                f"temp_{variant}_get" in self._device.registers
                and self._device.get_register_enabled(f"temp_{variant}_get")
                and self._device.get_register_value(f"temp_{variant}_get")
            ):
                self._temperature_get_key = f"temp_{variant}_get"
                break

        self._temperature_set_key = None
        for variant in DEVICE_VARIANTS:
            if (
                f"temp_{variant}_set" in self._device.registers
                and self._device.get_register_enabled(f"temp_{variant}_set")
                and self._device.get_register_value(f"temp_{variant}_set")
            ):
                self._temperature_set_key = f"temp_{variant}_set"
                break

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._device.id_device

    @property
    def name(self):
        """Return the name of the device, if any."""
        return self._device.name

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        if self._device.get_register_value("status_get") in [1, 2]:
            return HVACAction.HEATING
        elif self._device.get_register_value("status_get") in [3, 4, 5]:
            return HVACAction.HEATING
        elif self._device.get_register_value("status_get") in [7, 8, 9]:
            return HVACAction.IDLE
        return HVACMode.OFF

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVACMode.HEAT, HVACMode.OFF]

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        if self._device.get_register_value("status_get") not in [0, 6]:
            return HVACMode.HEAT
        return HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()

    @property
    def fan_mode(self):
        """Return fan mode."""
        return str(self._device.get_register_value_description("power_set"))

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        fan_modes = []
        for x in range(
            self._device.get_register_value_min("power_set"),
            (self._device.get_register_value_max("power_set") + 1),
        ):
            fan_modes.append(
                str(self._device.get_register_value_options("power_set").get(x, x))
            )
        return fan_modes

    async def async_turn_off(self):
        """Turn device off."""
        try:
            await self._device.set_register_value_description(
                "status_managed_get", "OFF"
            )
            await self.coordinator.async_request_refresh()
        except AguaIOTError as err:
            _LOGGER.error("Failed to turn off device, error: %s", err)

    async def async_turn_on(self):
        """Turn device on."""
        try:
            await self._device.set_register_value_description(
                "status_managed_get", "ON"
            )
            await self.coordinator.async_request_refresh()
        except AguaIOTError as err:
            _LOGGER.error("Failed to turn on device, error: %s", err)

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        try:
            await self._device.set_register_value_description("power_set", fan_mode)
            await self.coordinator.async_request_refresh()
        except AguaIOTError as err:
            _LOGGER.error("Failed to set fan mode, error: %s", err)

    @property
    def min_temp(self):
        """Return the minimum temperature to set."""
        return self._device.get_register_value_min(self._temperature_set_key)

    @property
    def max_temp(self):
        """Return the maximum temperature to set."""
        return self._device.get_register_value_max(self._temperature_set_key)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.get_register_value(self._temperature_get_key)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.get_register_value(self._temperature_set_key)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        try:
            await self._device.set_register_value(
                self._temperature_set_key, temperature
            )
            await self.coordinator.async_request_refresh()
        except (ValueError, AguaIOTError) as err:
            _LOGGER.error("Failed to set temperature, error: %s", err)

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._device.get_register(self._temperature_set_key).get("step", 1)


class AguaIOTCanalizationDevice(AguaIOTClimateDevice):
    def __init__(self, coordinator, device, canalization):
        CoordinatorEntity.__init__(self, coordinator)
        self._device = device
        self._target = canalization

    @property
    def unique_id(self):
        return f"{self._device.id_device}_{self._target}"

    @property
    def name(self):
        return f"{self._device.name} {self._target.replace('_', ' ')}"

    @property
    def supported_features(self):
        features = 0
        if f"{self._target}_temp_air_set" in self._device.registers:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if f"{self._target}_set" in self._device.registers:
            ClimateEntityFeature.PRESET_MODE
        if f"{self._target}_vent_set" in self._device.registers:
            features |= ClimateEntityFeature.FAN_MODE

        return features

    @property
    def fan_mode(self):
        """Return fan mode."""
        return str(
            self._device.get_register_value_description(f"{self._target}_vent_set")
        )

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        fan_modes = []
        for x in range(
            self._device.get_register_value_min(f"{self._target}_vent_set"),
            (self._device.get_register_value_max(f"{self._target}_vent_set") + 1),
        ):
            fan_modes.append(
                str(
                    self._device.get_register_value_options(
                        f"{self._target}_vent_set"
                    ).get(x, x)
                )
            )
        return fan_modes

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        try:
            await self._device.set_register_value_description(
                f"{self._target}_vent_set", fan_mode
            )
            await self.coordinator.async_request_refresh()
        except AguaIOTError as err:
            _LOGGER.error("Failed to set fan mode, error: %s", err)

    @property
    def hvac_action(self):
        if (
            f"{self._target}_vent_set" in self._device.registers
            and int(self._device.get_register_value(f"{self._target}_vent_set")) > 0
        ):
            return HVACAction.FAN
        return HVACAction.OFF

    @property
    def hvac_modes(self):
        return [HVACMode.FAN_ONLY]

    @property
    def hvac_mode(self):
        return HVACMode.FAN_ONLY

    async def async_set_hvac_mode(self, hvac_mode):
        pass

    @property
    def preset_modes(self):
        preset_modes = []
        for x in range(
            self._device.get_register_value_min(f"{self._target}_set"),
            (self._device.get_register_value_max(f"{self._target}_set") + 1),
        ):
            preset_modes.append(
                self._device.get_register_value_options(f"{self._target}_set").get(x, x)
            )
        return preset_modes

    @property
    def preset_mode(self):
        return self._device.get_register_value_description(f"{self._target}_set")

    @property
    def min_temp(self):
        """Return the minimum temperature to set."""
        return self._device.get_register_value_min(f"{self._target}_temp_air_set")

    @property
    def max_temp(self):
        """Return the maximum temperature to set."""
        return self._device.get_register_value_max(f"{self._target}_temp_air_set")

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.get_register_value(f"{self._target}_temp_air_set")

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.get_register_value(f"{self._target}_temp_air_get")

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        try:
            await self._device.set_register_value(
                f"{self._target}_temp_air_set", temperature
            )
            await self.coordinator.async_request_refresh()
        except (ValueError, AguaIOTError) as err:
            _LOGGER.error("Failed to set temperature, error: %s", err)

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._device.get_register(f"{self._target}_temp_air_set").get("step", 1)


class AguaIOTFanDevice(AguaIOTClimateDevice):
    def __init__(self, coordinator, device, multifan):
        CoordinatorEntity.__init__(self, coordinator)
        self._device = device
        self._target = multifan

    @property
    def unique_id(self):
        return f"{self._device.id_device}_{self._target}"

    @property
    def name(self):
        return f"{self._device.name} {self._target.replace('_', ' ')}"

    @property
    def supported_features(self):
        return ClimateEntityFeature.FAN_MODE

    @property
    def icon(self):
        return "mdi:fan"

    @property
    def fan_mode(self):
        """Return fan mode."""
        return str(self._device.get_register_value_description(f"{self._target}_set"))

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        fan_modes = []
        for x in range(
            self._device.get_register_value_min(f"{self._target}_set"),
            (self._device.get_register_value_max(f"{self._target}_set") + 1),
        ):
            fan_modes.append(
                str(
                    self._device.get_register_value_options(f"{self._target}_set").get(
                        x, x
                    )
                )
            )
        return fan_modes

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        try:
            await self._device.set_register_value_description(
                f"{self._target}_set", fan_mode
            )
            await self.coordinator.async_request_refresh()
        except AguaIOTError as err:
            _LOGGER.error("Failed to set fan mode, error: %s", err)

    @property
    def hvac_action(self):
        if (
            f"{self._target}_set" in self._device.registers
            and int(self._device.get_register_value(f"{self._target}_set")) > 0
        ):
            return HVACAction.FAN
        return HVACAction.OFF

    @property
    def hvac_modes(self):
        return [HVACMode.FAN_ONLY]

    @property
    def hvac_mode(self):
        return HVACMode.FAN_ONLY

    async def async_set_hvac_mode(self, hvac_mode):
        pass
