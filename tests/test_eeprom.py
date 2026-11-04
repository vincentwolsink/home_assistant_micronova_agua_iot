"""EEPROM budgets survive restarts and fail closed on storage errors."""

from types import SimpleNamespace

import pytest

from tests.helpers import load_component_module

eeprom = load_component_module("eeprom")


@pytest.fixture
def budget_env(monkeypatch, eeprom_hass):
    now = [100000.0]
    monkeypatch.setattr(eeprom.time, "time", lambda: now[0])
    return eeprom_hass, now


@pytest.mark.asyncio
async def test_daily_limit_restart_and_stove_isolation(budget_env):
    hass, now = budget_env
    guard = eeprom.EepromBudget(hass, "one")
    for _ in range(eeprom.DEFAULT_DAILY_LIMIT):
        await guard.reserve()
    restarted = eeprom.EepromBudget(hass, "one")
    with pytest.raises(eeprom.AguaIOTError, match="limit reached"):
        await restarted.reserve()
    await eeprom.EepromBudget(hass, "two").reserve()
    now[0] += 86400
    await restarted.reserve()


@pytest.mark.asyncio
async def test_daily_limit_and_clock_rollback(budget_env):
    hass, now = budget_env
    guard = eeprom.EepromBudget(hass, "one")
    for _ in range(eeprom.DEFAULT_DAILY_LIMIT):
        await guard.reserve()
        now[0] += 3600
    with pytest.raises(eeprom.AguaIOTError, match="limit reached"):
        await guard.reserve()
    now[0] -= 20000
    with pytest.raises(eeprom.AguaIOTError, match="limit reached"):
        await guard.reserve()
    now[0] += 86400 + 20000
    await guard.reserve()


@pytest.mark.asyncio
async def test_silent_storage_failure_blocks_reservation(budget_env, monkeypatch):
    hass, _ = budget_env
    guard = eeprom.EepromBudget(hass, "one")

    async def discard(_data):
        pass

    monkeypatch.setattr(guard.store, "async_save", discard)
    with pytest.raises(eeprom.AguaIOTError, match="No command was sent"):
        await guard.reserve()
    assert len(guard.history) == 1


@pytest.mark.asyncio
async def test_ram_write_ignores_the_budget(budget_env):
    hass, _ = budget_env
    hass.data = {}
    await eeprom.reserve_eeprom_write(hass, "DEV_01", [33])
    assert hass.data == {}


@pytest.mark.asyncio
async def test_cloud_and_mqtt_share_one_stove_budget(budget_env):
    hass, now = budget_env
    hass.data = {}
    for _ in range(eeprom.DEFAULT_DAILY_LIMIT):
        await eeprom.reserve_eeprom_write(hass, "DEV_01", [32768])
        now[0] += 3600
    with pytest.raises(eeprom.AguaIOTError, match="limit reached"):
        await eeprom.reserve_eeprom_write(
            hass, "DEV_01", [32768], legacy_id="AABBCCDDEEFF"
        )


@pytest.mark.asyncio
async def test_old_mqtt_history_still_counts(budget_env):
    hass, now = budget_env
    hass.data = {}
    old = eeprom.Store(hass, 1, "aguaiot.mqtt.AABBCCDDEEFF.eeprom")
    await old.async_save([now[0]] * eeprom.DEFAULT_DAILY_LIMIT)
    with pytest.raises(eeprom.AguaIOTError, match="limit reached"):
        await eeprom.reserve_eeprom_write(
            hass, "DEV_01", [32768], legacy_id="AABBCCDDEEFF"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("data", ["bad", [True], [float("nan")], [-1]])
async def test_invalid_history_blocks_writes(budget_env, data):
    hass, _ = budget_env
    guard = eeprom.EepromBudget(hass, "one")
    await guard.store.async_save(data)
    with pytest.raises(eeprom.AguaIOTError, match="No command was sent"):
        await guard.reserve()


@pytest.mark.asyncio
async def test_configured_limits_can_be_raised_on_an_existing_budget(budget_env):
    hass, now = budget_env
    device = SimpleNamespace(id_device="DEV_01", product_serial="AABBCCDDEEFF")
    # Existing installations have no per-stove setting and are enabled by default.
    for _ in range(eeprom.DEFAULT_DAILY_LIMIT):
        await eeprom.reserve_device_write(hass, device, [32893])
    with pytest.raises(eeprom.AguaIOTError, match="limit reached"):
        await eeprom.reserve_device_write(hass, device, [32893])
    limits = {"max_eeprom_writes_per_day": 200}
    for _ in range(200 - eeprom.DEFAULT_DAILY_LIMIT):
        await eeprom.reserve_device_write(hass, device, [32893], limits=limits)
    with pytest.raises(eeprom.AguaIOTError, match="200 commands per day"):
        await eeprom.reserve_device_write(hass, device, [32893], limits=limits)
    # Lowering the limit immediately applies to the already stored history.
    with pytest.raises(eeprom.AguaIOTError, match="10 commands per day"):
        await eeprom.reserve_device_write(hass, device, [32893])
    # The daily window frees the budget again.
    now[0] += 86400
    await eeprom.reserve_device_write(hass, device, [32893])


@pytest.mark.asyncio
async def test_concurrent_attempts_cannot_exceed_the_budget(budget_env):
    import asyncio

    hass, _ = budget_env
    results = await asyncio.gather(
        *(
            eeprom.reserve_eeprom_write(hass, "one", [32768])
            for _ in range(eeprom.DEFAULT_DAILY_LIMIT + 10)
        ),
        return_exceptions=True,
    )
    assert (
        sum(not isinstance(result, Exception) for result in results)
        == eeprom.DEFAULT_DAILY_LIMIT
    )
    assert all(
        isinstance(result, eeprom.AguaIOTError)
        for result in results
        if isinstance(result, Exception)
    )


@pytest.mark.asyncio
async def test_corrupt_history_is_not_treated_as_a_new_budget(budget_env):
    from pathlib import Path

    hass, _ = budget_env
    budget = eeprom.EepromBudget(hass, "corrupt")
    Path(budget.store.path + ".corrupt.test").write_text("unreadable")
    with pytest.raises(eeprom.AguaIOTError, match="No command was sent"):
        await budget.reserve()
