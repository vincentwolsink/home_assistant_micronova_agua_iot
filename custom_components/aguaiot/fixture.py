"""Fixture-backed Agua IOT client for development.

Set the ``AGUAIOT_FIXTURES`` environment variable to enable fixture mode:

* ``1``/``true``/``yes``/``on`` loads every ``*.json`` file from the
  default ``fixtures`` directory.
* Any other value is used as a path to a fixture directory or to a single
  fixture file.

Relative paths are resolved against the integration directory, the current
working directory and the Home Assistant configuration directory. This means
the default ``fixtures`` directory is ``custom_components/aguaiot/fixtures``,
next to the integration code.

Each fixture is exposed as its own device. Writes are simulated in memory:
register values change after the next update, but nothing is written to the
fixture file or sent to a stove.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from .aguaiot import AguaIOTError, Device, update_devices

_LOGGER = logging.getLogger(__name__)

ENV_FIXTURES = "AGUAIOT_FIXTURES"
COMPONENT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = COMPONENT_DIR.parent.parent
DEFAULT_FIXTURES_PATH = Path("fixtures")

_FALSE_VALUES = {"", "0", "false", "no", "off"}
_TRUE_VALUES = {"1", "true", "yes", "on"}


def get_fixture_source() -> Path | None:
    """Return the configured fixture path, or None when fixture mode is off."""
    value = os.environ.get(ENV_FIXTURES)
    if value is None:
        return None

    value = value.strip()
    if value.lower() in _FALSE_VALUES:
        return None
    if value.lower() in _TRUE_VALUES:
        return _default_fixture_path()

    return _resolve_fixture_path(value)


def _default_fixture_path() -> Path:
    """Return the fixtures directory inside the integration."""
    return Path(os.path.normpath(COMPONENT_DIR / DEFAULT_FIXTURES_PATH))


def _resolve_fixture_path(value: str) -> Path:
    """Resolve a fixture path, also when it is relative.

    Relative paths are checked against the integration directory, the current
    working directory and the Home Assistant configuration directory. This
    makes values like ``fixtures`` or ``../../fixtures`` work regardless of
    where Home Assistant was started from.
    """
    path = Path(value).expanduser()
    if path.is_absolute():
        return Path(os.path.normpath(path))

    candidates = [COMPONENT_DIR / path, Path.cwd() / path, CONFIG_DIR / path]
    for candidate in candidates:
        if candidate.exists():
            return Path(os.path.normpath(candidate))

    # Nothing matched; report the intended location in the error message.
    return Path(os.path.normpath(candidates[0]))


def create_fixture_client(**kwargs) -> FixtureAguaIOT | None:
    """Return a fixture client when fixture mode is enabled, else None."""
    source = get_fixture_source()
    if source is None:
        return None

    return FixtureAguaIOT(
        source,
        air_temp_fix=kwargs.get("air_temp_fix", False),
        reading_error_fix=kwargs.get("reading_error_fix", False),
        language=kwargs.get("language") or "ENG",
    )


def _raw_data_from_register_map(register_map) -> dict[int, int]:
    """Build the raw register word values from a fixture register map.

    Registers may share an offset using different masks (bit packing). The
    fixture value_raw values are already masked, so combine them into the
    full word.
    """
    raw_data: dict[int, int] = {}
    for register in register_map.values():
        if "offset" not in register:
            continue

        offset = int(register["offset"])
        mask = int(register.get("mask", 0xFFFF))
        value_raw = register.get("value_raw")
        # A null value_raw means the register was not read from the device.
        # Skip it so the Device reports it as unread instead of as zero.
        if value_raw is None:
            continue
        value = int(value_raw)
        current = raw_data.get(offset, 0)
        raw_data[offset] = (current & ~mask) | (value & mask)

    return raw_data


class FixtureAguaIOT:
    """Agua IOT client that reads devices from JSON fixtures.

    It implements the parts of :class:`~.aguaiot.aguaiot` used by the
    coordinator, devices and entities, so it can be used as a drop-in
    replacement for development without a stove.
    """

    def __init__(
        self,
        fixture_path=None,
        air_temp_fix=False,
        reading_error_fix=False,
        language="ENG",
        **kwargs,
    ):
        # Accept and ignore the keyword arguments of the real client so this
        # class can be constructed from the same configuration.
        self.fixture_path = (
            _default_fixture_path()
            if fixture_path is None
            else _resolve_fixture_path(str(fixture_path))
        )
        self.air_temp_fix = air_temp_fix
        self.reading_error_fix = reading_error_fix
        self.language = language
        self.devices: list[Device] = []
        self._raw_data: dict[str, dict[int, int]] = {}

    async def connect(self):
        """Load all configured fixtures as devices."""
        _LOGGER.warning(
            "Agua IOT fixture mode enabled, loading fixtures from %s",
            self.fixture_path,
        )

        self.devices = []
        self._raw_data = {}

        for index, (name, register_map) in enumerate(self._load_fixtures(), start=1):
            device = Device(
                id=index,
                id_device=f"fixture_{name}",
                id_product=index,
                product_serial=f"FIXTURE-{name}",
                name=name,
                is_online=True,
                name_product=name,
                id_registers_map=1,
                aguaiot=self,
                device_info={},
                register_map=register_map,
            )
            raw_data = _raw_data_from_register_map(register_map)
            self._raw_data[device.id_device] = raw_data
            device.apply_raw_data(raw_data)
            self.devices.append(device)

    async def update(self):
        """Refresh every device from its in-memory register values."""
        await update_devices(self.devices)

    async def validate_local_connection(self) -> dict:
        """Accept the local connection check; fixtures are always available."""
        return {"fixture": True}

    async def _fetch_device_information(self, device):
        """Return the raw register values of a fixture device."""
        return self._raw_data[device.id_device]

    async def _request_writing(self, device, items):
        """Apply a write to the in-memory register values of a device."""
        raw_data = self._raw_data[device.id_device]

        for key, value in items.items():
            register = device.get_register(key)
            offset = int(register["offset"])
            mask = int(register["mask"])
            current = raw_data.get(offset, 0)
            raw_data[offset] = (current & ~mask) | (int(value) & mask)

        _LOGGER.debug("Fixture write on %s: %s", device.name, items)

    def _load_fixtures(self):
        """Yield the name and register map of every fixture."""
        path = self.fixture_path
        if not path.exists():
            raise AguaIOTError(f"Fixture path does not exist: {path}")

        files = (
            [path]
            if path.is_file()
            else sorted(item for item in path.iterdir() if item.suffix == ".json")
        )
        if not files:
            raise AguaIOTError(f"No JSON fixtures found in: {path}")

        for file in files:
            try:
                with file.open(encoding="utf-8") as fixture_file:
                    register_map = json.load(fixture_file)
            except (OSError, ValueError) as err:
                raise AguaIOTError(f"Could not load fixture {file}: {err}") from err

            if not isinstance(register_map, dict):
                raise AguaIOTError(f"Invalid fixture {file}: expected a JSON object")

            yield file.stem, register_map
