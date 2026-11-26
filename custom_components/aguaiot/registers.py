"""Resolve vendor specific naming variants of registers.

Vendors do not name the registers of the same function consistently. The set
and get registers of one function often differ by a variant digit, and the
digit can be in different places:

* ``temp_air_set`` / ``temp_air2_get`` (digit after a word)
* ``vent_front_set`` / ``vent_front2_get``, but also ``vent_front2_set`` /
  ``vent_front_get`` (the other way around)
* ``canalization_dx_set`` / ``canalization_2dx_get`` (digit before a word)

A register key is reduced to a canonical form by dropping these variant
digits. Registers sharing a canonical form are aliases of each other, so a
lookup for one finds the others when the register itself does not exist.

Only digits glued to a word are variant digits. Numeric segments such as the
``1`` in ``canalization_1_set`` or ``thermostat_contact_1_get`` identify a
separate unit and are kept. The first segment is kept as well: it names the
function (``fan2_mode_set`` is a second fan, not a variant of ``fan_mode_set``).
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Iterable

# A variant digit at the end (``front2``) or start (``2dx``) of a word.
_TRAILING_VARIANT = re.compile(r"^([a-z]+)[2-9]$")
_LEADING_VARIANT = re.compile(r"^[2-9]([a-z]+)$")


def canonical_key(key: str) -> str:
    """Return the key without variant digits.

    The last segment is the register role (``get``, ``set``, ``enable``, ...)
    and is never changed.
    """
    segments = key.lower().split("_")
    for i in range(1, len(segments) - 1):
        match = _TRAILING_VARIANT.match(segments[i]) or _LEADING_VARIANT.match(
            segments[i]
        )
        if match:
            segments[i] = match.group(1)
    return "_".join(segments)


def with_role(key: str, role: str) -> str:
    """Return the key with its role (last segment) replaced."""
    return f"{key.rsplit('_', 1)[0]}_{role}"


class RegisterAliases:
    """Index of the register keys of a device by their canonical form."""

    def __init__(self, keys: Iterable[str]) -> None:
        self._keys = set(keys)
        self._index: dict[str, list[str]] = {}
        for key in sorted(self._keys):
            self._index.setdefault(canonical_key(key), []).append(key)

    def aliases(self, key: str) -> list[str]:
        """Return the existing registers matching the key, best match first.

        The key itself comes first when it exists. The other aliases follow
        with the variant free name first, then in alphabetical order, which
        also orders the variants by digit (``air2`` before ``air3``).
        """
        key = key.lower()
        canonical = canonical_key(key)
        candidates = sorted(
            self._index.get(canonical, []),
            key=lambda k: (k != key, k != canonical, k),
        )
        return candidates

    def find(
        self, key: str, predicate: Callable[[str], bool] | None = None
    ) -> str | None:
        """Return the best existing register for the key, or None.

        With a predicate, the first alias for which it returns True is used.
        """
        for candidate in self.aliases(key):
            if predicate is None or predicate(candidate):
                return candidate
        return None


def bind_descriptions(device, descriptions, check_enabled=True):
    """Bind entity descriptions to the registers of a device.

    A description matches its own key first and a naming variant of it
    otherwise. The returned descriptions have their key set to the register
    they are bound to. Exact matches are bound before variants, so a variant
    never takes a register another description names directly, and each
    register is bound only once.

    With check_enabled, only enabled registers are bound, unless the
    description has ``force_enabled`` set.
    """
    descriptions = list(descriptions)
    claimed: set[str] = set()
    bound: dict[int, str] = {}

    for exact in (True, False):
        for index, description in enumerate(descriptions):
            if index in bound:
                continue
            candidates = device.register_aliases(description.key)
            if exact:
                candidates = [k for k in candidates if k == description.key.lower()]
            for key in candidates:
                if key in claimed:
                    continue
                if (
                    check_enabled
                    and not getattr(description, "force_enabled", False)
                    and not device.get_register_enabled(key)
                ):
                    continue
                claimed.add(key)
                bound[index] = key
                break

    return [
        dataclasses.replace(descriptions[i], key=bound[i])
        if bound[i] != descriptions[i].key
        else descriptions[i]
        for i in sorted(bound)
    ]
