"""Test the fixture-backed Agua IOT client."""

import json
from pathlib import Path

import pytest

from tests.helpers import load_component_module

fixture_module = load_component_module("fixture")

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class TestFixtureSource:
    def test_default_path_is_fixtures(self):
        assert fixture_module.DEFAULT_FIXTURES_PATH == Path("fixtures")

    def test_default_path_is_inside_integration(self):
        assert fixture_module._default_fixture_path() == (
            fixture_module.COMPONENT_DIR / "fixtures"
        )

    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv(fixture_module.ENV_FIXTURES, raising=False)
        assert fixture_module.get_fixture_source() is None

    def test_disabled_explicitly(self, monkeypatch):
        monkeypatch.setenv(fixture_module.ENV_FIXTURES, "0")
        assert fixture_module.get_fixture_source() is None

    def test_enabled_uses_default_path(self, monkeypatch):
        monkeypatch.setenv(fixture_module.ENV_FIXTURES, "1")
        assert (
            fixture_module.get_fixture_source()
            == fixture_module._default_fixture_path()
        )

    def test_custom_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv(fixture_module.ENV_FIXTURES, str(tmp_path))
        assert fixture_module.get_fixture_source() == tmp_path

    def test_relative_path_from_config_dir(self, monkeypatch, tmp_path):
        config_dir = tmp_path / "config"
        fixtures_dir = config_dir / "fixtures"
        fixtures_dir.mkdir(parents=True)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        monkeypatch.setattr(fixture_module, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(
            fixture_module,
            "COMPONENT_DIR",
            config_dir / "custom_components" / "aguaiot",
        )
        monkeypatch.chdir(elsewhere)
        monkeypatch.setenv(fixture_module.ENV_FIXTURES, "fixtures")

        assert fixture_module.get_fixture_source() == fixtures_dir

    def test_relative_path_from_component_dir(self, monkeypatch, tmp_path):
        config_dir = tmp_path / "config"
        fixtures_dir = config_dir / "fixtures"
        fixtures_dir.mkdir(parents=True)
        component_dir = config_dir / "custom_components" / "aguaiot"
        component_dir.mkdir(parents=True)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        monkeypatch.setattr(fixture_module, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(fixture_module, "COMPONENT_DIR", component_dir)
        monkeypatch.chdir(elsewhere)
        monkeypatch.setenv(fixture_module.ENV_FIXTURES, "../../fixtures")

        assert fixture_module.get_fixture_source() == fixtures_dir

    def test_create_client_from_environment(self, monkeypatch):
        monkeypatch.setenv(fixture_module.ENV_FIXTURES, str(FIXTURES_DIR))

        client = fixture_module.create_fixture_client(air_temp_fix=True, language="ITA")

        assert isinstance(client, fixture_module.FixtureAguaIOT)
        assert client.fixture_path == FIXTURES_DIR
        assert client.air_temp_fix is True
        assert client.language == "ITA"

    def test_create_client_disabled(self, monkeypatch):
        monkeypatch.setenv(fixture_module.ENV_FIXTURES, "0")

        assert fixture_module.create_fixture_client() is None


class TestLoadFixtures:
    @pytest.mark.asyncio
    async def test_every_fixture_becomes_a_device(self, fixture_names):
        client = fixture_module.FixtureAguaIOT(FIXTURES_DIR)
        await client.connect()

        assert [device.name for device in client.devices] == fixture_names
        assert len({device.id_device for device in client.devices}) == len(
            fixture_names
        )

    @pytest.mark.asyncio
    async def test_single_fixture_file(self):
        client = fixture_module.FixtureAguaIOT(FIXTURES_DIR / "ravelli.json")
        await client.connect()

        assert len(client.devices) == 1
        assert client.devices[0].name == "ravelli"

    @pytest.mark.asyncio
    async def test_register_values_match_fixture(self, fixture_data):
        client = fixture_module.FixtureAguaIOT(FIXTURES_DIR / "ravelli.json")
        await client.connect()

        expected = fixture_data["ravelli"]["temp_air_get"]
        register = client.devices[0].get_register("temp_air_get")
        assert register["value_raw"] == expected["value_raw"]
        assert register["value"] == expected["value"]

    @pytest.mark.asyncio
    async def test_missing_fixture_path_raises(self):
        client = fixture_module.FixtureAguaIOT(FIXTURES_DIR / "does-not-exist")

        with pytest.raises(fixture_module.AguaIOTError):
            await client.connect()


class TestWrites:
    @pytest.mark.asyncio
    async def test_write_updates_value_in_memory_only(self):
        client = fixture_module.FixtureAguaIOT(FIXTURES_DIR / "ravelli.json")
        await client.connect()
        device = client.devices[0]

        assert device.get_register_value("power_set") == 3

        await device.set_register_value("power_set", 4)
        await client.update()

        assert device.get_register_value("power_set") == 4

        # The fixture file must not be modified.
        fixture = json.loads((FIXTURES_DIR / "ravelli.json").read_text())
        assert fixture["power_set"]["value_raw"] == "3"


def test_raw_data_combines_registers_sharing_an_offset():
    raw_data = fixture_module._raw_data_from_register_map(
        {
            "low": {"offset": 1, "mask": 255, "value_raw": "42"},
            "high": {"offset": 1, "mask": 65280, "value_raw": "256"},
        }
    )

    assert raw_data == {1: 0x012A}
