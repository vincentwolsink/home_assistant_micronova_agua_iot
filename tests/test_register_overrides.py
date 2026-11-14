"""Test the register overrides applied by the local transports."""

from tests.helpers import load_component_module

overrides_module = load_component_module("register_overrides")
apply_register_overrides = overrides_module.apply_register_overrides

BRONPI_MAP_ID = "B89772DB-3E76-4A4F-B03C-A1626EA1B49E"


class TestApplyRegisterOverrides:
    def test_adds_pellet_sensor_for_bronpi_map(self):
        register_map = {"status_get": {"offset": 33}}

        result = apply_register_overrides(BRONPI_MAP_ID, register_map)

        assert result["status_get"] == {"offset": 33}
        assert result["ris_pellet_ris_get"]["offset"] == 159
        assert result["ris_pellet_ris_get"]["formula"] == "IF(#<37,1,0)"

    def test_map_id_match_is_case_insensitive(self):
        result = apply_register_overrides(BRONPI_MAP_ID.lower(), {})

        assert "ris_pellet_ris_get" in result

    def test_does_not_modify_input_map(self):
        register_map = {"status_get": {"offset": 33}}

        apply_register_overrides(BRONPI_MAP_ID, register_map)

        assert register_map == {"status_get": {"offset": 33}}

    def test_keeps_register_already_in_map(self):
        existing = {"offset": 42, "formula": "#"}
        register_map = {"ris_pellet_ris_get": existing}

        result = apply_register_overrides(BRONPI_MAP_ID, register_map)

        assert result["ris_pellet_ris_get"] is existing

    def test_other_map_is_unchanged(self):
        register_map = {"status_get": {"offset": 33}}

        assert apply_register_overrides(5, register_map) is register_map

    def test_missing_map_is_unchanged(self):
        assert apply_register_overrides(BRONPI_MAP_ID, None) is None

    def test_returned_registers_are_copies(self):
        first = apply_register_overrides(BRONPI_MAP_ID, {})
        first["ris_pellet_ris_get"]["offset"] = 1

        second = apply_register_overrides(BRONPI_MAP_ID, {})

        assert second["ris_pellet_ris_get"]["offset"] == 159
