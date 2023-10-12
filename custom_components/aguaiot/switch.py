from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import SWITCHES, DOMAIN
from .aguaiot import (
    ConnectionError,
    AguaIOTError,
    UnauthorizedError,
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    agua = hass.data[DOMAIN][entry.entry_id]["agua"]

    switches = []
    for device in agua.devices:
        for switch in SWITCHES:
            if switch.key in device.registers and device.get_register_enabled(
                switch.key
            ):
                switches.append(AguaIOTHeatingSwitch(coordinator, device, switch))

    async_add_entities(switches, True)


class AguaIOTHeatingSwitch(CoordinatorEntity, SwitchEntity):
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
    def is_on(self):
        """Return the state of the sensor."""
        return bool(self._device.get_register_value(self.entity_description.key))

    async def async_turn_off(self):
        """Turn device off."""
        try:
            await self._device.set_register_value(self.entity_description.key, 0)
            await self.coordinator.async_request_refresh()
        except AguaIOTError as err:
            _LOGGER.error(
                "Failed to turn off '%s', error: %s",
                f"{self._device.name} {self.entity_description.name}",
                err,
            )

    async def async_turn_on(self):
        """Turn device on."""
        try:
            await self._device.set_register_value(self.entity_description.key, 1)
            await self.coordinator.async_request_refresh()
        except AguaIOTError as err:
            _LOGGER.error(
                "Failed to turn on '%s', error: %s",
                f"{self._device.name} {self.entity_description.name}",
                err,
            )
