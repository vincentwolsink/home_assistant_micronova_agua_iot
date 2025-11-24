"""Support for Micronova Agua IOT heating devices."""

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from .coordinator import AguaIOTDataUpdateCoordinator
from .const import DOMAIN, PLATFORMS


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the AguaIOT integration."""
    if DOMAIN in config:
        for entry_config in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry_config
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up AguaIOT entry."""
    coordinator = AguaIOTDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
    )
    config_entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Services
    async def async_close_connection(event: Event) -> None:
        """Close AguaIOT connection on HA Stop."""
        # await agua.close()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
