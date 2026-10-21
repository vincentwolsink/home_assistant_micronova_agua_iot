import importlib
import os
import sys
import types

COMPONENT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "custom_components", "aguaiot")
)
COMPONENT_PACKAGE = "aguaiot_component"


def load_component_module(module_name, stubbed_modules=None):
    """Load a module of the custom component without importing the package.

    The __init__.py of the integration imports Home Assistant specific
    modules, which are not needed to test the individual modules.

    Modules listed in stubbed_modules are replaced by a stub exposing the
    given attributes, so a module can be imported without the optional
    dependencies of the stubbed module.
    """
    if COMPONENT_PACKAGE not in sys.modules:
        package = types.ModuleType(COMPONENT_PACKAGE)
        package.__path__ = [COMPONENT_DIR]
        sys.modules[COMPONENT_PACKAGE] = package

    for name, attributes in (stubbed_modules or {}).items():
        stub_name = f"{COMPONENT_PACKAGE}.{name}"
        if stub_name not in sys.modules:
            stub = types.ModuleType(stub_name)
            for attribute, value in attributes.items():
                setattr(stub, attribute, value)
            sys.modules[stub_name] = stub

    return importlib.import_module(f"{COMPONENT_PACKAGE}.{module_name}")


# Load the aguaiot module directly to avoid the __init__.py import cascade
_aguaiot_module = load_component_module("aguaiot")

Device = _aguaiot_module.Device
aguaiot = _aguaiot_module.aguaiot
AguaIOTError = _aguaiot_module.AguaIOTError
AguaIOTUnauthorized = _aguaiot_module.AguaIOTUnauthorized
AguaIOTUpdateError = _aguaiot_module.AguaIOTUpdateError


def compute_information_dict(register_map):
    """Build information dict from fixture register map.

    Registers may share an offset using different masks (bit packing).
    Value_raw values are already masked - so we need to combine them
    bitwise into the full word value.
    """
    info = {}
    for reg in register_map.values():
        offset = reg.get("offset")
        value_raw = reg.get("value_raw", "0")
        mask = reg.get("mask", 65535)
        if offset is not None:
            raw_int = int(value_raw)
            existing = info.get(offset)
            # The raw value already has mask applied, so place it
            # back into the word at the mask's bit positions.
            # We need to find a value where existing_mask bits = existing_value
            # and new_mask bits = raw_int.
            if existing is not None:
                # Check if they can coexist (non-overlapping masks or consistent values)
                if existing & mask == raw_int:
                    # Already consistent
                    continue
                # Bitwise OR them - each value should occupy non-overlapping mask bits
                info[offset] = existing | raw_int
            else:
                info[offset] = raw_int
    return info


def build_device_from_fixture(aguaiot_instance, fixture_name, register_map):
    raw_data = compute_information_dict(register_map)
    device = Device(
        id=1,
        id_device=fixture_name,
        id_product=1,
        product_serial=f"SERIAL-{fixture_name}",
        name=fixture_name,
        is_online=True,
        name_product=fixture_name,
        id_registers_map=1,
        aguaiot=aguaiot_instance,
        device_info={},
        register_map=register_map,
    )
    device._Device__register_dict = device._Device__build_register_dict(raw_data)
    return device


def build_device_without_values(aguaiot_instance, fixture_name, register_map):
    """Build a device that has not been read successfully (yet).

    The register map is available, but no register values have been read.
    """
    return Device(
        id=1,
        id_device=fixture_name,
        id_product=1,
        product_serial=f"SERIAL-{fixture_name}",
        name=fixture_name,
        is_online=True,
        name_product=fixture_name,
        id_registers_map=1,
        aguaiot=aguaiot_instance,
        device_info={},
        register_map=register_map,
    )
