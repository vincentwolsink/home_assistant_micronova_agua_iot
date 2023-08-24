from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import NUMBERS, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    agua = hass.data[DOMAIN][entry.entry_id]["agua"]

    numbers = []
    for device in agua.devices:
        for number in NUMBERS:
            if getattr(device, number.key, None) is not None:
                numbers.append(AguaIOTHeatingNumber(coordinator, device, number))

    async_add_entities(numbers, True)


class AguaIOTHeatingNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, device, description):
        """Initialize the thermostat."""
        CoordinatorEntity.__init__(self, coordinator)
        self._device = device
        self.entity_description = description

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._device.id_device}_{self.entity_description.key}"

    @property
    def name(self):
        """Return the name of the device, if any."""
        return f"{self._device.name} {self.entity_description.name}"

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
        return getattr(self._device, self.entity_description.key)

    @property
    def native_min_value(self):
        return getattr(self._device, f"min_{self.entity_description.key}")

    @property
    def native_max_value(self):
        return getattr(self._device, f"max_{self.entity_description.key}")

    async def async_set_native_value(self, value):
        try:
            await self.hass.async_add_executor_job(
                setattr,
                self._device,
                self.entity_description.key,
                value,
            )
            await self.coordinator.async_request_refresh()
        except (ValueError, AguaIOTError) as err:
            _LOGGER.error("Failed to set value, error: %s", err)
