"""Support for Agua IOT heating devices."""

import logging
import re
import copy
import numbers
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
    AIR_VARIANTS,
    WATER_VARIANTS,
    CLIMATE_CANALIZATIONS,
    MODE_PELLETS,
    MODE_WOOD,
    STATUS_OFF,
    STATUS_IDLE,
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
        stove = AguaIOTAirDevice(coordinator, device)
        entities.append(stove)

        if any(f"temp_{variant}_set" in device.registers for variant in WATER_VARIANTS):
            entities.append(AguaIOTWaterDevice(coordinator, device, stove))

        for canalization in CLIMATE_CANALIZATIONS:
            for c_found in [
                m
                for i in device.registers
                for m in [re.match(canalization.key, i.lower())]
                if m
            ]:
                if (
                    (
                        canalization.key_enable
                        and device.get_register_enabled(
                            canalization.key_enable.format(id=c_found.group(1))
                        )
                    )
                    or (
                        canalization.key2_enable
                        and device.get_register_enabled(
                            canalization.key2_enable.format(id=c_found.group(1))
                        )
                    )
                    or (
                        not canalization.key_enable
                        and device.get_register_enabled(c_found.group(0))
                    )
                ):
                    c_copy = copy.deepcopy(canalization)
                    c_copy.key = c_found.group(0)
                    for key in [
                        "name",
                        "key_temp_set",
                        "key_temp_get",
                        "key_temp2_get",
                        "key_vent_set",
                    ]:
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


class AguaIOTAirDevice(AguaIOTClimateDevice):
    """Representation of an Agua IOT heating device."""

    def __init__(self, coordinator, device):
        """Initialize the thermostat."""
        CoordinatorEntity.__init__(self, coordinator)
        self._enable_turn_on_off_backwards_compatibility = False
        self._device = device
        self._hybrid = "power_wood_set" in device.registers

        self._temperature_get_key = None
        for variant in AIR_VARIANTS:
            if (
                f"temp_{variant}_get" in self._device.registers
                and self._device.get_register_enabled(f"temp_{variant}_get")
                and self._device.get_register_value(f"temp_{variant}_get")
            ):
                self._temperature_get_key = f"temp_{variant}_get"
                break

        self._temperature_set_key = None
        for variant in AIR_VARIANTS:
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
            ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
        )
        if self._hybrid:
            features = features | ClimateEntityFeature.PRESET_MODE
        return features

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        if (
            str(self._device.get_register_value_description("status_get")).upper()
            in STATUS_IDLE
        ):
            return HVACAction.IDLE
        elif (
            self._device.get_register_value("status_get") == 0
            or str(self._device.get_register_value_description("status_get")).upper()
            in STATUS_OFF
        ):
            return HVACAction.OFF
        return HVACAction.HEATING

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVACMode.HEAT, HVACMode.OFF]

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        if (
            self._device.get_register_value("status_get") == 0
            or str(self._device.get_register_value_description("status_get")).upper()
            in STATUS_OFF
        ):
            return HVACMode.OFF
        return HVACMode.HEAT

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
        value = self._device.get_register_value_description(self._temperature_get_key)
        if isinstance(value, numbers.Number):
            return value

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.current_temperature:
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
                },
                limit_value_raw=True,
            )
        except (ValueError, AguaIOTError) as err:
            _LOGGER.error("Failed to set value, error: %s", err)


class AguaIOTWaterDevice(AguaIOTClimateDevice):
    """Representation of an Agua IOT heating device."""

    def __init__(self, coordinator, device, parent):
        """Initialize the thermostat."""
        CoordinatorEntity.__init__(self, coordinator)
        self._enable_turn_on_off_backwards_compatibility = False
        self._device = device
        self._parent = parent

        self._temperature_get_key = None
        for variant in WATER_VARIANTS:
            if (
                f"temp_{variant}_get" in self._device.registers
                and self._device.get_register_enabled(f"temp_{variant}_get")
                and self._device.get_register_value(f"temp_{variant}_get")
            ):
                self._temperature_get_key = f"temp_{variant}_get"
                break

        self._temperature_set_key = None
        for variant in WATER_VARIANTS:
            if (
                f"temp_{variant}_set" in self._device.registers
                and self._device.get_register_enabled(f"temp_{variant}_set")
                and self._device.get_register_value(f"temp_{variant}_set")
            ):
                self._temperature_set_key = f"temp_{variant}_set"
                break

    @property
    def unique_id(self):
        return f"{self._device.id_device}_water"

    @property
    def name(self):
        return f"{self._device.name} Water"

    @property
    def icon(self):
        return "mdi:water"

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = (
            ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TARGET_TEMPERATURE
        )
        return features

    @property
    def hvac_action(self):
        return self._parent.hvac_action

    @property
    def hvac_modes(self):
        return self._parent.hvac_modes

    @property
    def hvac_mode(self):
        return self._parent.hvac_mode

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()

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
        value = self._device.get_register_value_description(self._temperature_get_key)
        if isinstance(value, numbers.Number):
            return value

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.current_temperature:
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
    def __init__(self, coordinator, device, description, parent):
        CoordinatorEntity.__init__(self, coordinator)
        self._enable_turn_on_off_backwards_compatibility = False
        self._device = device
        self._parent = parent
        self.entity_description = description
        self._fan_register = self.entity_description.key

        if (
            self.entity_description.key_vent_set
            and self.entity_description.key_vent_set in self._device.registers
        ):
            self._fan_register = self.entity_description.key_vent_set

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
            self.entity_description.key_temp_set
            and self.entity_description.key_temp_set in self._device.registers
            and self._device.get_register_enabled(self.entity_description.key_temp_set)
        ):
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if (
            self.entity_description.key_vent_set
            and self.entity_description.key_vent_set in self._device.registers
        ):
            features |= ClimateEntityFeature.PRESET_MODE

        return features

    @property
    def fan_mode(self):
        """Return fan mode."""
        return str(self._device.get_register_value_description(self._fan_register))

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        fan_modes = []
        for x in range(
            self._device.get_register_value_min(self._fan_register),
            (self._device.get_register_value_max(self._fan_register) + 1),
        ):
            fan_modes.append(
                str(
                    self._device.get_register_value_options(self._fan_register).get(
                        x, x
                    )
                )
            )
        return fan_modes

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        try:
            await self._device.set_register_value_description(
                self._fan_register, fan_mode
            )
            await self.coordinator.async_request_refresh()
        except AguaIOTError as err:
            _LOGGER.error("Failed to set fan mode, error: %s", err)

    @property
    def preset_modes(self):
        return list(
            self._device.get_register_value_options(
                self.entity_description.key
            ).values()
        )

    @property
    def preset_mode(self):
        return self._device.get_register_value_description(self.entity_description.key)

    async def async_set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
        try:
            await self._device.set_register_value_description(
                self.entity_description.key, preset_mode
            )
            await self.coordinator.async_request_refresh()
        except AguaIOTError as err:
            _LOGGER.error("Failed to set preset mode, error: %s", err)

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
            if self.current_temperature:
                return self._device.get_register_value(
                    self.entity_description.key_temp_set
                )

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if (
            self.entity_description.key_temp_get in self._device.registers
            and self._device.get_register_enabled(self.entity_description.key_temp_get)
        ):
            value = self._device.get_register_value_description(
                self.entity_description.key_temp_get
            )
            if isinstance(value, numbers.Number):
                return value
        elif (
            self.entity_description.key_temp2_get
            and self.entity_description.key_temp2_get in self._device.registers
            and self._device.get_register_enabled(self.entity_description.key_temp2_get)
        ):
            value = self._device.get_register_value_description(
                self.entity_description.key_temp2_get
            )
            if isinstance(value, numbers.Number):
                return value

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
