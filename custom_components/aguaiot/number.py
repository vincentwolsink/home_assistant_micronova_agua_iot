import logging
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import NUMBERS, DOMAIN
from .aguaiot import AguaIOTError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = config_entry.runtime_data
    agua = coordinator.agua

    numbers = []
    for device in agua.devices:
        hybrid = "power_wood_set" in device.registers

        for number in NUMBERS:
            if (
                number.key in device.registers
                and (number.force_enabled or device.get_register_enabled(number.key))
                and (
                    (number.hybrid_only and hybrid)
                    or (number.hybrid_exclude and not hybrid)
                    or (not number.hybrid_only and not number.hybrid_exclude)
                )
            ):
                numbers.append(AguaIOTHeatingNumber(coordinator, device, number))

    async_add_entities(numbers, True)


class AguaIOTHeatingNumber(CoordinatorEntity, NumberEntity):
    """Number entity"""

    _attr_has_entity_name = True

    def __init__(self, coordinator, device, description):
        """Initialize the thermostat."""
        super().__init__(coordinator)
        self._device = device
        self.entity_description = description

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._device.id_device}_{self.entity_description.key}"

    @property
    def name(self):
        """Return the name of the device, if any."""
        return self.entity_description.name

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
    def native_value(self):
        """Return the state of the sensor."""
        return self._device.get_register_value(self.entity_description.key)

    @property
    def native_min_value(self):
        return self._device.get_register_value_min(self.entity_description.key)

    @property
    def native_max_value(self):
        return self._device.get_register_value_max(self.entity_description.key)

    async def async_set_native_value(self, value):
        try:
            await self._device.set_register_value(self.entity_description.key, value)
            await self.coordinator.async_request_refresh()
        except (ValueError, AguaIOTError) as err:
            _LOGGER.error("Failed to set value, error: %s", err)
