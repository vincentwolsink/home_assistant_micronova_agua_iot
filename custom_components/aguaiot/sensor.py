import re
import copy
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.entity import DeviceInfo
from .const import SENSORS, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    agua = hass.data[DOMAIN][entry.entry_id]["agua"]

    sensors = []
    for device in agua.devices:
        hybrid = "power_wood_set" in device.registers

        for sensor in SENSORS:
            if (
                sensor.key in device.registers
                and (sensor.force_enabled or device.get_register_enabled(sensor.key))
                and (not sensor.hybrid_only or hybrid)
            ):
                sensors.append(AguaIOTHeatingSensor(coordinator, device, sensor))

    async_add_entities(sensors, True)


class AguaIOTHeatingSensor(CoordinatorEntity, SensorEntity):
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
        return self._device.get_register_value_description(self.entity_description.key)

    @property
    def extra_state_attributes(self):
        """Expose plain value as extra attribute when needed."""
        if self._device.get_register_value_options(self.entity_description.key):
            return {
                "raw_value": self._device.get_register_value(
                    self.entity_description.key
                ),
            }

    @property
    def options(self):
        if self.entity_description.device_class == SensorDeviceClass.ENUM:
            options = sorted(
                list(
                    set(
                        self._device.get_register_value_options(
                            self.entity_description.key
                        ).values()
                    )
                )
            )
            cur_value = self._device.get_register_value_description(
                self.entity_description.key
            )
            if cur_value not in options:
                options.append(cur_value)

            return options
