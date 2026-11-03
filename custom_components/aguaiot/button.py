import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .aguaiot import AguaIOTError
from .const import BUTTONS, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = config_entry.runtime_data
    agua = coordinator.agua

    buttons = []
    for device in agua.devices:
        for button in BUTTONS:
            # The enable register depends on the stove state, so it drives
            # availability instead of creation.
            if button.key in device.registers:
                buttons.append(AguaIOTHeatingButton(coordinator, device, button))

    async_add_entities(buttons, True)


class AguaIOTHeatingButton(CoordinatorEntity, ButtonEntity):
    """Button entity"""

    _attr_has_entity_name = True

    def __init__(self, coordinator, device, description):
        """Initialize the button."""
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
    def available(self):
        """Only available when the stove accepts the command."""
        key = self.entity_description.key
        # Without a read value the stove state, and so the enable state, is unknown
        return (
            super().available
            and self._device.get_register_value(key) is not None
            and self._device.get_register_enabled(key)
        )

    async def async_press(self):
        """Press the button."""
        try:
            await self._device.set_register_value(self.entity_description.key, 0)
            await self.coordinator.async_request_refresh()
        except AguaIOTError as err:
            _LOGGER.error(
                "Failed to press '%s', error: %s",
                f"{self._device.name} {self.entity_description.name}",
                err,
            )
