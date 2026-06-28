"""Constants for the Renson Arean integration."""

from datetime import timedelta

DOMAIN = "renson_arean"

CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_MODBUS_SLAVE = "modbus_slave"

DEFAULT_MODBUS_SLAVE = 41

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

PLATFORMS = ["climate", "sensor", "switch", "binary_sensor"]

# Preset names as shown on the wall thermostat and in the Renson One app
PRESET_SCHEDULE = "schedule"
PRESET_AWAY = "away"
PRESET_MANUAL = "manual"

# Modbus slave 41 register 3 — preset mapping
PRESET_MAP: dict[str, int] = {
    PRESET_SCHEDULE: 0,
    PRESET_AWAY: 1,
    PRESET_MANUAL: 5,
}

# Gateway preset name → HA preset name
OM_PRESET_TO_HA: dict[str, str] = {
    "auto": PRESET_SCHEDULE,
    "away": PRESET_AWAY,
    "manual": PRESET_MANUAL,
    "override": PRESET_MANUAL,
}

# Outputs with known HVAC function
KNOWN_OUTPUTS: dict[int, dict[str, str]] = {
    1: {"name": "Bathroom valve", "device_class": "opening"},
    2: {"name": "Three-way valve", "device_class": "opening"},
    3: {"name": "Central heating pump", "device_class": "running"},
    4: {"name": "Recirculation pump", "device_class": "running"},
}

# Outputs with unknown function — shown as diagnostic, disabled by default
UNKNOWN_OUTPUTS: list[int] = [0, 5, 7]

# Output 6 is a dimmer (bypass valve percentage), shown as sensor
BYPASS_OUTPUT_ID = 6
