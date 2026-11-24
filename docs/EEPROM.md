# EEPROM protection

Micronova controllers store some stove settings in EEPROM memory. EEPROM has a limited number of write cycles, so repeatedly writing the same setting can eventually wear out the controller's memory. To reduce that risk, the integration limits how many EEPROM write commands it sends to each stove per day.

The protection is enabled by default for every connection method. Cloud, Bluetooth, and local MQTT writes all share the same per-stove budget and persisted history.

## Why the limit exists

The limit is a safety net against accidental or excessive writing, for example from an automation that updates an EEPROM-backed setting every few seconds. It is not a restriction on normal stove use: typical manual changes stay well below the default limit.

The integration only counts writes that it sends itself. Changes made with another app, a physical control panel, or another integration are not visible to this counter.

## What counts as an EEPROM write

- Writes to register offsets at or above `32768` are EEPROM writes.
- A command that writes several registers counts as one attempt.
- Reading EEPROM registers, including normal polling, does not consume write cycles and is not counted.
- RAM writes are not counted.

## Daily budget

- Each stove has its own budget.
- The default limit is `20` attempts per day.
- The counter resets at local midnight.
- The limit is configurable in the integration options as `max_eeprom_writes_per_day`. Any positive integer is accepted; there is no fixed upper limit.
- Cloud, Bluetooth, and local MQTT share the budget, and the history survives Home Assistant restarts.
- Existing installations without stored EEPROM settings still get the protection with the default limit.

## Failure handling

An attempt is saved before the command is handed to the transport. It remains counted if the write fails, times out, or is cancelled, because a failed response does not prove that the write was not applied. The integration does not automatically retry local writes.

If the stored history cannot be read or saved, EEPROM writes are blocked rather than allowing an unlimited number of writes.

## Diagnostic sensor

Every stove exposes a diagnostic sensor named **EEPROM Writes (today)**. It shows the number of EEPROM write attempts currently counted against the daily budget.
