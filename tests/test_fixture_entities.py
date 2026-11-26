"""Guard the entities created for every fixture.

Vendors name registers inconsistently, and the register resolution decides
which entities a stove gets. This test makes sure a change to it does not
silently add, remove or rename entities of a known stove.

Run with ``UPDATE_SNAPSHOTS=1`` to regenerate the snapshot after an
intended change, and review the diff.
"""

import json
import os
from unittest.mock import MagicMock

import pytest

from tests.conftest import FIXTURES_DIR
from tests.helpers import build_device_from_fixture, load_component_module

pytest.importorskip(
    "homeassistant.components.climate", reason="homeassistant is required"
)

PLATFORMS = [
    "binary_sensor",
    "button",
    "climate",
    "number",
    "select",
    "sensor",
    "switch",
]
SNAPSHOT = os.path.join(os.path.dirname(__file__), "snapshots", "fixture_entities.json")

modules = {platform: load_component_module(platform) for platform in PLATFORMS}


def read_snapshot():
    with open(SNAPSHOT) as f:
        return json.load(f)


def write_snapshot(entities):
    os.makedirs(os.path.dirname(SNAPSHOT), exist_ok=True)
    with open(SNAPSHOT, "w") as f:
        json.dump(entities, f, indent=2)
        f.write("\n")


async def fixture_entities(aguaiot_mock, name, register_map, monkeypatch):
    device = build_device_from_fixture(aguaiot_mock, name, register_map)
    coordinator = MagicMock()
    coordinator.agua.devices = [device]
    config_entry = MagicMock()
    config_entry.runtime_data = coordinator
    monkeypatch.setattr(
        modules["climate"].entity_platform,
        "async_get_current_platform",
        MagicMock,
    )

    entities = {}
    for platform in PLATFORMS:
        created = []
        await modules[platform].async_setup_entry(
            None, config_entry, lambda new, update=False, out=created: out.extend(new)
        )
        for entity in created:
            entities[f"{platform}.{entity.unique_id}"] = entity.name
    return dict(sorted(entities.items()))


@pytest.mark.asyncio
async def test_fixture_entities(aguaiot_mock, fixture_data, monkeypatch):
    actual = {
        name: await fixture_entities(aguaiot_mock, name, register_map, monkeypatch)
        for name, register_map in fixture_data.items()
    }

    if os.environ.get("UPDATE_SNAPSHOTS"):
        write_snapshot(actual)
    expected = read_snapshot()

    assert sorted(actual) == sorted(expected), (
        f"Fixtures changed, regenerate the snapshot ({FIXTURES_DIR})"
    )
    for name in expected:
        assert actual[name] == expected[name], name
