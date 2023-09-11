from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

TO_REDACT = {
    CONF_PASSWORD,
    CONF_EMAIL,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    agua = hass.data[DOMAIN][entry.entry_id]["agua"]

    devices = {}
    for device in agua.devices:
        devices[device.name] = device.full_data_map

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "devices": devices,
    }
