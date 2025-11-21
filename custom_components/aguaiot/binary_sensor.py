from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import BINARY_SENSORS, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = config_entry.runtime_data
    agua = coordinator.agua

    sensors = []
    for device in agua.devices:
        hybrid = "power_wood_set" in device.registers

        for sensor in BINARY_SENSORS:
            if (
                sensor.key in device.registers
                and (sensor.force_enabled or device.get_register_enabled(sensor.key))
                and (not sensor.hybrid_only or hybrid)
            ):
                sensors.append(AguaIOTHeatingBinarySensor(coordinator, device, sensor))

    async_add_entities(sensors, True)


class AguaIOTHeatingBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor entity"""

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
    def icon(self):
        if self.is_on:
            return self.entity_description.icon_on or self.entity_description.icon
        else:
            return self.entity_description.icon

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
