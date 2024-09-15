import re
import copy
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import SENSORS, DOMAIN, TEMPERATURE_SENSORS


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

        for temperature_sensor in TEMPERATURE_SENSORS:
            for t_found in [
                m
                for i in device.registers
                for m in [re.match(temperature_sensor.key, i.lower())]
                if m and device.get_register_enabled(m.group(0))
            ]:
                t_copy = copy.deepcopy(temperature_sensor)
                t_copy.key = t_found.group(0)
                for key in ["name"]:
                    if getattr(t_copy, key):
                        setattr(
                            t_copy,
                            key,
                            getattr(t_copy, key).format_map(t_found.groupdict()),
                        )

                sensors.append(AguaIOTHeatingSensor(coordinator, device, t_copy))

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
                )
            }
