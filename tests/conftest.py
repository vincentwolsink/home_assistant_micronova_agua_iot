import json
import os

import pytest

from tests.helpers import aguaiot, build_device_from_fixture

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def load_all_fixtures():
    fixtures = {}
    for fname in sorted(os.listdir(FIXTURES_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(FIXTURES_DIR, fname)
        with open(path) as f:
            fixtures[fname.replace(".json", "")] = json.load(f)
    return fixtures


@pytest.fixture(scope="session")
def fixture_data():
    return load_all_fixtures()


@pytest.fixture
def fixture_names(fixture_data):
    return sorted(fixture_data.keys())


@pytest.fixture
def aguaiot_mock():
    inst = aguaiot(
        api_url="https://example.com",
        customer_code="000000",
        email="test@example.com",
        password="test",
        unique_id="test-uuid",
    )
    return inst


@pytest.fixture
def devices_from_fixtures(aguaiot_mock, fixture_data):
    devices = {}
    for name, reg_map in fixture_data.items():
        devices[name] = build_device_from_fixture(aguaiot_mock, name, reg_map)
    return devices


@pytest.fixture
def eeprom_hass(monkeypatch, tmp_path):
    """A file-backed EEPROM history without a running HA instance."""
    from types import SimpleNamespace

    from tests.helpers import load_component_module

    class FakeStore:
        def __init__(self, hass, version, key, **kwargs):
            self.path = str(tmp_path / key)

        async def async_load(self):
            try:
                with open(self.path) as source:  # noqa: ASYNC230 - tiny local test fixture
                    return json.load(source)["data"]
            except FileNotFoundError:
                return None

        async def async_save(self, data):
            with open(self.path, "w") as target:  # noqa: ASYNC230 - tiny local test fixture
                json.dump({"data": data}, target)

    async def execute(fn, *args):
        return fn(*args)

    eeprom = load_component_module("eeprom")
    monkeypatch.setattr(eeprom, "Store", FakeStore)
    return SimpleNamespace(data={}, async_add_executor_job=execute)
