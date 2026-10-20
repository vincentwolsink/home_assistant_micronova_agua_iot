"""Agua IOT options helpers."""

CONF_DEVICE_FIXES = "device_fixes"


def get_device_fix(options, key):
    """Return a device fix option, nested in its section or legacy flat."""
    device_fixes = options.get(CONF_DEVICE_FIXES) or {}
    if key in device_fixes:
        return device_fixes[key]
    return options.get(key, False)
