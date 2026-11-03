"""Persistent per-stove EEPROM write limits."""

import asyncio
import json
import math
import time
from pathlib import Path

from homeassistant.helpers.storage import Store

from .aguaiot import AguaIOTError

# Default used when no limit has been configured.
DEFAULT_DAILY_LIMIT = 10
EEPROM_OFFSET_THRESHOLD = 32768


def clean_mac(value):
    """Return a 12-digit MAC, or None."""
    if not isinstance(value, str) or not value:
        return None
    mac = value.replace(":", "").replace("-", "").strip().upper()
    if len(mac) == 12 and all(char in "0123456789ABCDEF" for char in mac):
        return mac
    return None


def legacy_mac_for(device, device_options, explicit=None):
    """Resolve the MAC address used by legacy MQTT write histories."""
    settings = (device_options or {}).get(str(getattr(device, "id_device", "")), {})
    return (
        clean_mac(explicit)
        or clean_mac(settings.get("device_mac"))
        or clean_mac(getattr(device, "product_serial", None))
    )


class EepromBudget:
    """Track EEPROM write attempts in a rolling daily window."""

    def __init__(self, hass, stove_id, legacy_id=None):
        self.hass = hass
        self.store = Store(hass, 1, f"aguaiot.{stove_id}.eeprom", atomic_writes=True)
        self.legacy_id = clean_mac(legacy_id) if legacy_id else None
        self.lock = asyncio.Lock()
        self.history = None

    def _path_exists(self, path):
        file_path = Path(path)
        return file_path.exists() or any(
            file_path.parent.glob(f"{file_path.name}.corrupt.*")
        )

    def _verify(self, history):
        with Path(self.store.path).open() as source:
            if json.load(source).get("data") != history:
                raise OSError("EEPROM reservation was not saved")

    async def _load(self, store):
        history = await store.async_load()
        if history is None and await self.hass.async_add_executor_job(
            self._path_exists, store.path
        ):
            raise ValueError("Unreadable EEPROM history")
        return history

    def _check_history(self, history):
        if not isinstance(history, list) or any(
            type(value) not in (float, int) or not math.isfinite(value) or value < 0
            for value in history
        ):
            raise ValueError("Invalid EEPROM history")

    async def reserve(self, daily_limit=DEFAULT_DAILY_LIMIT):
        async with self.lock:
            try:
                if type(daily_limit) is not int or daily_limit < 1:
                    raise ValueError("EEPROM limit must be a positive integer")
                if self.history is None:
                    history = await self._load(self.store)
                    if history is None and self.legacy_id:
                        legacy = Store(
                            self.hass,
                            1,
                            f"aguaiot.mqtt.{self.legacy_id}.eeprom",
                            atomic_writes=True,
                        )
                        history = await self._load(legacy)
                    if history is None:
                        history = []
                    self._check_history(history)
                    self.history = history
                now = time.time()
                # Keep future reservations if the system clock moves backwards.
                self.history = [stamp for stamp in self.history if now - stamp < 86400]
                if len(self.history) >= daily_limit:
                    raise AguaIOTError(
                        "EEPROM write limit reached for this stove. "
                        f"The limit is {daily_limit} commands per day. "
                        "Try again later."
                    )
                self.history.append(now)
                await self.store.async_save(self.history)
                await self.hass.async_add_executor_job(self._verify, self.history)
                return now
            except (OSError, ValueError, TypeError) as err:
                raise AguaIOTError(
                    "Cannot verify the EEPROM write budget. No command was sent."
                ) from err


async def reserve_eeprom_write(hass, stove_id, offsets, *, legacy_id=None, limits=None):
    """Reserve a write attempt for commands containing EEPROM offsets."""
    parsed = []
    for offset in offsets:
        value = int(offset)
        if value < 0 or value > 65535:
            raise AguaIOTError("Invalid register offset")
        parsed.append(value)
    if not any(value >= EEPROM_OFFSET_THRESHOLD for value in parsed):
        return
    if hass is None or not stove_id:
        raise AguaIOTError(
            "Cannot verify the EEPROM write budget. No command was sent."
        )
    budgets = hass.data.setdefault("aguaiot", {}).setdefault("eeprom_budgets", {})
    budget = budgets.get(stove_id)
    if budget is None:
        budget = EepromBudget(hass, stove_id, legacy_id=legacy_id)
        budgets[stove_id] = budget
    limits = limits or {}
    return await budget.reserve(
        daily_limit=limits.get("max_eeprom_writes_per_day", DEFAULT_DAILY_LIMIT),
    )


async def reserve_device_write(
    hass, device, offsets, device_options, explicit_mac=None, *, limits=None
):
    """Apply the shared stove budget before a cloud, Bluetooth or MQTT write."""
    return await reserve_eeprom_write(
        hass,
        str(getattr(device, "id_device", "") or ""),
        offsets,
        legacy_id=legacy_mac_for(device, device_options, explicit=explicit_mac),
        limits=limits,
    )
