"""Support for Agua IOT heating devices."""
import logging
import re
import copy

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
    CLIMATE_CANALIZATIONS,
    CLIMATE_FANS,
    MODE_PELLETS,
    MODE_WOOD,
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

        for canalization in CLIMATE_CANALIZATIONS:
            for canalization_found in [
                m.group(1)
                for i in device.registers
                for m in [re.match(canalization.key, i.lower())]
                if m and device.get_register_enabled(m.group(0))
            ]:
                canalization_copy = copy.deepcopy(canalization)
                canalization_copy.key = canalization_found
                entities.append(
                    AguaIOTCanalizationDevice(coordinator, device, canalization_copy)
                )

        for fan in CLIMATE_FANS:
            for fan_found in [
                m[0]
                for i in device.registers
                for m in [re.match(fan.key, i.lower())]
                if m and device.get_register_enabled(m[0])
            ]:
                fan_copy = copy.deepcopy(fan)
                fan_copy.key = fan_found
                entities.append(AguaIOTFanDevice(coordinator, device, fan_copy))

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
        self._hybrid = "power_wood_set" in device.registers

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
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        )
        if self._hybrid:
            features = features | ClimateEntityFeature.PRESET_MODE
        return features

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        if self._device.get_register_value("status_get") in [1, 2, 3, 4, 5, 13, 14]:
            return HVACAction.HEATING
        elif self._device.get_register_value("status_get") in [0, 6]:
            return HVACAction.OFF
        return HVACAction.IDLE

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
    def hybrid_mode(self):
        return (
            MODE_WOOD
            if self._hybrid and self._device.get_register_enabled("power_wood_set")
            else MODE_PELLETS
        )

    @property
    def fan_mode(self):
        """Return fan mode."""
        power_register = (
            "power_wood_set" if self.hybrid_mode == MODE_WOOD else "power_set"
        )
        return str(self._device.get_register_value_description(power_register))

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        fan_modes = []
        power_register = (
            "power_wood_set" if self.hybrid_mode == MODE_WOOD else "power_set"
        )
        for x in range(
            self._device.get_register_value_min(power_register),
            (self._device.get_register_value_max(power_register) + 1),
        ):
            fan_modes.append(
                str(self._device.get_register_value_options(power_register).get(x, x))
            )
        return fan_modes

    @property
    def preset_modes(self):
        return [self.hybrid_mode]

    @property
    def preset_mode(self):
        return self.hybrid_mode

    async def async_set_preset_mode(self, preset_mode):
        # The stove will pick the correct mode.
        pass

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
    def __init__(self, coordinator, device, description):
        CoordinatorEntity.__init__(self, coordinator)
        self._device = device
        self.entity_description = description
        self.entity_description.name = self.entity_description.key.replace("_", " ")

    @property
    def unique_id(self):
        return f"{self._device.id_device}_{self.entity_description.key}"

    @property
    def name(self):
        return f"{self._device.name} {self.entity_description.name}"

    @property
    def supported_features(self):
        features = 0
        if f"{self.entity_description.key}_temp_air_set" in self._device.registers:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if f"{self.entity_description.key}_set" in self._device.registers:
            ClimateEntityFeature.PRESET_MODE
        if f"{self.entity_description.key}_vent_set" in self._device.registers:
            features |= ClimateEntityFeature.FAN_MODE

        return features

    @property
    def fan_mode(self):
        """Return fan mode."""
        return str(
            self._device.get_register_value_description(
                f"{self.entity_description.key}_vent_set"
            )
        )

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        fan_modes = []
        for x in range(
            self._device.get_register_value_min(
                f"{self.entity_description.key}_vent_set"
            ),
            (
                self._device.get_register_value_max(
                    f"{self.entity_description.key}_vent_set"
                )
                + 1
            ),
        ):
            fan_modes.append(
                str(
                    self._device.get_register_value_options(
                        f"{self.entity_description.key}_vent_set"
                    ).get(x, x)
                )
            )
        return fan_modes

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        try:
            await self._device.set_register_value_description(
                f"{self.entity_description.key}_vent_set", fan_mode
            )
            await self.coordinator.async_request_refresh()
        except AguaIOTError as err:
            _LOGGER.error("Failed to set fan mode, error: %s", err)

    @property
    def hvac_action(self):
        if (
            f"{self.entity_description.key}_vent_set" in self._device.registers
            and int(
                self._device.get_register_value(
                    f"{self.entity_description.key}_vent_set"
                )
            )
            > 0
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
            self._device.get_register_value_min(f"{self.entity_description.key}_set"),
            (
                self._device.get_register_value_max(
                    f"{self.entity_description.key}_set"
                )
                + 1
            ),
        ):
            preset_modes.append(
                self._device.get_register_value_options(
                    f"{self.entity_description.key}_set"
                ).get(x, x)
            )
        return preset_modes

    @property
    def preset_mode(self):
        return self._device.get_register_value_description(
            f"{self.entity_description.key}_set"
        )

    @property
    def min_temp(self):
        """Return the minimum temperature to set."""
        return self._device.get_register_value_min(
            f"{self.entity_description.key}_temp_air_set"
        )

    @property
    def max_temp(self):
        """Return the maximum temperature to set."""
        return self._device.get_register_value_max(
            f"{self.entity_description.key}_temp_air_set"
        )

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.get_register_value(
            f"{self.entity_description.key}_temp_air_set"
        )

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.get_register_value(
            f"{self.entity_description.key}_temp_air_get"
        )

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        try:
            await self._device.set_register_value(
                f"{self.entity_description.key}_temp_air_set", temperature
            )
            await self.coordinator.async_request_refresh()
        except (ValueError, AguaIOTError) as err:
            _LOGGER.error("Failed to set temperature, error: %s", err)

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._device.get_register(
            f"{self.entity_description.key}_temp_air_set"
        ).get("step", 1)


class AguaIOTFanDevice(AguaIOTClimateDevice):
    def __init__(self, coordinator, device, description):
        CoordinatorEntity.__init__(self, coordinator)
        self._device = device
        self.entity_description = description
        self.entity_description.name = self.entity_description.key.rsplit("_", 1)[
            0
        ].replace("_", " ")

    @property
    def unique_id(self):
        return f"{self._device.id_device}_{self.entity_description.key}"

    @property
    def name(self):
        return f"{self._device.name} {self.entity_description.name}"

    @property
    def supported_features(self):
        return ClimateEntityFeature.FAN_MODE

    @property
    def icon(self):
        return "mdi:fan"

    @property
    def fan_mode(self):
        """Return fan mode."""
        return str(
            self._device.get_register_value_description(self.entity_description.key)
        )

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        fan_modes = []
        for x in range(
            self._device.get_register_value_min(self.entity_description.key),
            (self._device.get_register_value_max(self.entity_description.key) + 1),
        ):
            fan_modes.append(
                str(
                    self._device.get_register_value_options(
                        self.entity_description.key
                    ).get(x, x)
                )
            )
        return fan_modes

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        try:
            await self._device.set_register_value_description(
                self.entity_description.key, fan_mode
            )
            await self.coordinator.async_request_refresh()
        except AguaIOTError as err:
            _LOGGER.error("Failed to set fan mode, error: %s", err)

    @property
    def hvac_action(self):
        if (
            self.entity_description.key in self._device.registers
            and int(self._device.get_register_value(self.entity_description.key)) > 0
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
