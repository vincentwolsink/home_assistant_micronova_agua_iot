import logging
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import SELECTS, DOMAIN
from .aguaiot import AguaIOTError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    agua = hass.data[DOMAIN][entry.entry_id]["agua"]

    selects = []
    for device in agua.devices:
        for select in SELECTS:
            if select.key in device.registers and device.get_register_enabled(
                select.key
            ):
                selects.append(AguaIOTHeatingSelect(coordinator, device, select))

    async_add_entities(selects, True)


class AguaIOTHeatingSelect(CoordinatorEntity, SelectEntity):
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
    def current_option(self):
        return self._device.get_register_value_description(self.entity_description.key)

    @property
    def options(self):
        return list(
            self._device.get_register_value_options(
                self.entity_description.key
            ).values()
        )

    async def async_select_option(self, option):
        try:
            await self._device.set_register_value_description(
                self.entity_description.key, option
            )
            await self.coordinator.async_request_refresh()
        except (ValueError, AguaIOTError) as err:
            _LOGGER.error("Failed to set value, error: %s", err)
