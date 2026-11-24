"""Failed setup attempts must not leave local client tasks subscribed."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.helpers import load_component_module

component = load_component_module("__init__")


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["refresh", "platforms", "cancel"])
async def test_failed_setup_closes_transport(monkeypatch, stage):
    hass, entry = MagicMock(), MagicMock()
    coordinator = MagicMock()
    coordinator.agua.close = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    error = asyncio.CancelledError() if stage == "cancel" else RuntimeError("failed")
    if stage == "platforms":
        hass.config_entries.async_forward_entry_setups.side_effect = error
    else:
        coordinator.async_config_entry_first_refresh.side_effect = error
    monkeypatch.setattr(
        component, "AguaIOTDataUpdateCoordinator", MagicMock(return_value=coordinator)
    )
    with pytest.raises(type(error)):
        await component.async_setup_entry(hass, entry)
    coordinator.agua.close.assert_awaited_once()
    entry.async_on_unload.assert_not_called()
