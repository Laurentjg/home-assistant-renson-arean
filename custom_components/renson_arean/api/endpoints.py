"""Every gateway path the integration uses, in one place.

Endpoints that exist but are unusable on gateway 3.14.0 are listed at the
bottom so nobody rediscovers them the hard way.
"""

from __future__ import annotations

LOGIN = "login"

# Identity and versions (§5.2)
GET_VERSION = "get_version"
GET_STATUS = "get_status"
GET_SYSTEM_STATUS = "get_system_status"
GET_FEATURES = "get_features"

# Topology (§10)
GET_MODULES_INFORMATION = "get_modules_information"
GET_PLUGINS = "get_plugins"

# State (§5.3, §5.2)
GET_OUTPUT_STATUS = "get_output_status"
GET_INPUT_STATUS = "get_input_status"
GET_PLUGIN_LOGS = "get_plugin_logs"

# Thermostat (§5.4)
GET_THERMOSTAT_GROUP_STATUS = "get_thermostat_group_status"
GET_THERMOSTAT_GROUP_CONFIGURATIONS = "get_thermostat_group_configurations"
SET_CURRENT_SETPOINT = "set_current_setpoint"
SET_THERMOSTAT_GROUP = "set_thermostat_group"

# Modbus write path of the RensonModbusBackend (§5.4)
WRITE_MODBUS_REGISTER = "write_modbus_register"


def plugin_config(app: str) -> str:
    """Path to the configuration of one app."""
    return f"plugins/{app}/get_config"


# Deliberately unused:
#   get_metrics / get_metric_definitions — 404 resp. an internal error (V-05, CN-10)
#   get_power_modules / get_realtime_power / get_total_energy — no energy metering (D-08)
#   get_sensor_status — exposes only the room temperature of RensonThermostat (V-03)
#   read_modbus_register — reading the RTU bus collides with the apps' polling (CN-01)
