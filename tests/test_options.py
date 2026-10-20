"""Test reading the device fixes options."""

import importlib.util
import os

import pytest

# Load options.py directly to avoid __init__.py import cascade
_OPTIONS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "custom_components", "aguaiot", "options.py"
)
_spec = importlib.util.spec_from_file_location("options_module", _OPTIONS_PATH)
_options_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_options_module)

CONF_DEVICE_FIXES = _options_module.CONF_DEVICE_FIXES
get_device_fix = _options_module.get_device_fix


class TestGetDeviceFix:
    @pytest.mark.parametrize("key", ["air_temp_fix", "reading_error_fix"])
    def test_nested_options(self, key):
        options = {CONF_DEVICE_FIXES: {key: True}}
        assert get_device_fix(options, key) is True

    @pytest.mark.parametrize("key", ["air_temp_fix", "reading_error_fix"])
    def test_legacy_flat_options(self, key):
        options = {key: True}
        assert get_device_fix(options, key) is True

    def test_nested_takes_precedence_over_flat(self):
        options = {
            "reading_error_fix": True,
            CONF_DEVICE_FIXES: {"reading_error_fix": False},
        }
        assert get_device_fix(options, "reading_error_fix") is False

    def test_missing_key_in_section_falls_back_to_flat(self):
        options = {
            "air_temp_fix": True,
            CONF_DEVICE_FIXES: {"reading_error_fix": True},
        }
        assert get_device_fix(options, "air_temp_fix") is True

    @pytest.mark.parametrize("options", [{}, {CONF_DEVICE_FIXES: {}}])
    def test_defaults_to_false(self, options):
        assert get_device_fix(options, "air_temp_fix") is False
