"""Support for Agua IOT heating devices."""
import logging
import re
import copy
from homeassistant.helpers import entity_platform, service
from homeassistant.util import dt
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
        stove = AguaIOTHeatingDevice(coordinator, device)
        entities.append(stove)

        for canalization in CLIMATE_CANALIZATIONS:
            for c_found in [
                m
                for i in device.registers
                for m in [re.match(canalization.key, i.lower())]
                if m and device.get_register_enabled(m.group(0))
            ]:
                c_copy = copy.deepcopy(canalization)
                c_copy.key = c_found.group(0)
                for key in ["name", "key_temp_set", "key_temp_get"]:
                    if getattr(c_copy, key):
                        setattr(
                            c_copy,
                            key,
                            getattr(c_copy, key).format_map(c_found.groupdict()),
                        )

                entities.append(
                    AguaIOTCanalizationDevice(coordinator, device, c_copy, stove)
                )

    async_add_entities(entities, True)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "sync_clock",
        {},
        "sync_clock",
    )


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
            if self._hybrid and self._device.get_register_enabled("real_power_wood_get")
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
        power_register = (
            "power_wood_set" if self.hybrid_mode == MODE_WOOD else "power_set"
        )
        try:
            await self._device.set_register_value_description(power_register, fan_mode)
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

    async def sync_clock(self):
        dt_now = dt.now()
        try:
            await self._device.set_register_values(
                {
                    "clock_hour_set": dt_now.hour,
                    "clock_minute_set": dt_now.minute,
                    "calendar_day_set": dt_now.day,
                    "calendar_month_set": dt_now.month,
                    "calendar_year_set": dt_now.year,
                }
            )
        except (ValueError, AguaIOTError) as err:
            _LOGGER.error("Failed to set value, error: %s", err)


class AguaIOTCanalizationDevice(AguaIOTClimateDevice):
    def __init__(self, coordinator, device, description, parent):
        CoordinatorEntity.__init__(self, coordinator)
        self._device = device
        self._parent = parent
        self.entity_description = description

    @property
    def unique_id(self):
        return f"{self._device.id_device}_{self.entity_description.key}"

    @property
    def name(self):
        return f"{self._device.name} {self.entity_description.name}"

    @property
    def supported_features(self):
        features = ClimateEntityFeature.FAN_MODE
        if (
            self.entity_description.key_temp_set in self._device.registers
            and self._device.get_register_enabled(self.entity_description.key_temp_set)
        ):
            features |= ClimateEntityFeature.TARGET_TEMPERATURE

        return features

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
        if int(self._device.get_register_value(self.entity_description.key)) > 0:
            return self._parent.hvac_action
        return HVACAction.OFF

    @property
    def hvac_modes(self):
        if int(self._device.get_register_value(self.entity_description.key)) > 0:
            return [self._parent.hvac_mode]
        return [HVACMode.OFF]

    @property
    def hvac_mode(self):
        if int(self._device.get_register_value(self.entity_description.key)) > 0:
            return self._parent.hvac_mode
        return HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode):
        pass

    @property
    def min_temp(self):
        """Return the minimum temperature to set."""
        if self.entity_description.key_temp_set in self._device.registers:
            return self._device.get_register_value_min(
                self.entity_description.key_temp_set
            )

    @property
    def max_temp(self):
        """Return the maximum temperature to set."""
        if self.entity_description.key_temp_set in self._device.registers:
            return self._device.get_register_value_max(
                self.entity_description.key_temp_set
            )

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.entity_description.key_temp_set in self._device.registers:
            return self._device.get_register_value(self.entity_description.key_temp_set)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self.entity_description.key_temp_get in self._device.registers:
            return self._device.get_register_value(self.entity_description.key_temp_get)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        try:
            await self._device.set_register_value(
                self.entity_description.key_temp_set, temperature
            )
            await self.coordinator.async_request_refresh()
        except (ValueError, AguaIOTError) as err:
            _LOGGER.error("Failed to set temperature, error: %s", err)

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        if self.entity_description.key_temp_set in self._device.registers:
            return self._device.get_register(self.entity_description.key_temp_set).get(
                "step", 1
            )
