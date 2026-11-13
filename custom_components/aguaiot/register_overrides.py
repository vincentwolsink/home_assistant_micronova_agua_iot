"""Registers that local transports can read but cloud register maps lack.

The cloud register map of a stove only lists the registers the vendor app
uses. Some stoves expose more useful values in RAM, such as the state of the
pellet level sensor. The local transports (MQTT and Bluetooth) read the
offsets listed in the register map, so adding a register to the map is enough
to read it. Cloud reads use a server defined buffer and never return these
offsets, so the overrides are only applied by the local transports.

Overrides are keyed by the id of the cloud register map and are only added
when the map does not already define the register.
"""

from __future__ import annotations

import copy
from typing import Any

REGISTER_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    # Bronpi "BRONPI PLUS RADIO" (tested on a Neva insert with a Navel 2.0
    # module). RAM offset 159 holds the capacitive pellet level sensor state:
    # around 220 while pellets cover the sensor, 8 once the level drops below
    # it. The remote then shows "DEPOSITO VAZIO" ("tank empty") while the
    # stove keeps burning the reserve.
    "B89772DB-3E76-4A4F-B03C-A1626EA1B49E": {
        "ris_pellet_ris_get": {
            "reg_key": "ris_pellet_ris_get",
            "reg_type": "GET",
            "offset": 159,
            "mask": 255,
            "formula": "IF(#<37,1,0)",
            "formula_inverse": "#",
            "is_hex": False,
            "is_word": False,
            "set_min": 0,
            "set_max": 255,
        },
    },
}


def apply_register_overrides(
    id_registers_map: Any, register_map: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Return the register map with the overrides for its map id added.

    Registers already present in the map are never replaced.
    """
    overrides = REGISTER_OVERRIDES.get(str(id_registers_map).upper())
    if not overrides or register_map is None:
        return register_map

    merged = dict(register_map)
    for key, register in overrides.items():
        if key not in merged:
            merged[key] = copy.deepcopy(register)
    return merged
