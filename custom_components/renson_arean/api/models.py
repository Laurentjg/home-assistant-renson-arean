"""Dataclasses and parsers for the gateway responses.

Every parser takes the raw decoded JSON and is defensive about missing fields:
the gateway is a moving target (§2.2) and a missing field must never raise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --- helpers -----------------------------------------------------------------


def _first(section: Any) -> dict[str, Any]:
    """Return the first entry of a plugin config section, or an empty dict.

    Plugin configuration sections are lists of one dict, but an app that has
    never been configured returns an empty list.
    """
    if isinstance(section, list) and section:
        entry = section[0]
        if isinstance(entry, dict):
            return entry
    return {}


def on_off(value: Any) -> bool | None:
    """Interpret the gateway's `On`/`Off` strings."""
    if value == "On":
        return True
    if value == "Off":
        return False
    return None


def as_float(value: Any) -> float | None:
    """Return `value` as a float, or None if it is not a number."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    """Return `value` as an int, or None if it is not a whole number."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# --- topology ----------------------------------------------------------------


@dataclass(frozen=True)
class GatewayVersion:
    """Firmware versions of the gateway itself (V-08)."""

    gateway: str | None = None
    master: str | None = None
    python_version: str | None = None


@dataclass(frozen=True)
class FirmwareUpdate:
    """One row of `get_system_status.updates.status_detail`."""

    firmware_type: str
    state: str | None
    current_version: str | None
    target_version: str | None
    module_address: str | None = None

    @property
    def update_available(self) -> bool:
        """True when the gateway reports a target other than the current version."""
        return bool(
            self.current_version
            and self.target_version
            and self.current_version != self.target_version
        )


@dataclass(frozen=True)
class ModuleInfo:
    """One module as reported by get_modules_information."""

    address: str
    source: str
    module_type: str
    hardware_type: str
    online: bool
    name: str | None = None
    firmware_version: str | None = None
    serial_number: str | None = None

    @property
    def is_physical(self) -> bool:
        """True for a module that physically sits on the bus.

        The Brain reports its own channels as internal master modules; those
        are an addressing layer, not a separate box (§2.3).
        """
        return self.hardware_type == "physical"


@dataclass(frozen=True)
class AppInfo:
    """One app as reported by get_plugins."""

    name: str
    version: str | None
    status: str | None
    interfaces: tuple[str, ...] = ()

    @property
    def running(self) -> bool:
        """True while the gateway reports the app as running."""
        return self.status == "RUNNING"


@dataclass(frozen=True)
class Topology:
    """Everything the topology coordinator collects (§6.2)."""

    version: GatewayVersion = field(default_factory=GatewayVersion)
    updates: tuple[FirmwareUpdate, ...] = ()
    modules: dict[str, ModuleInfo] = field(default_factory=dict)
    apps: dict[str, AppInfo] = field(default_factory=dict)

    @property
    def hvac_module(self) -> ModuleInfo | None:
        """The HVAC module, if the gateway reports one."""
        for module in self.modules.values():
            if module.module_type == "hvac":
                return module
        return None

    @property
    def offline_modules(self) -> tuple[str, ...]:
        """Addresses of modules that are known but no longer answering."""
        return tuple(
            address for address, module in self.modules.items() if not module.online
        )


def parse_version(raw: dict[str, Any]) -> GatewayVersion:
    """Parse get_version."""
    return GatewayVersion(
        gateway=raw.get("gateway"),
        master=raw.get("master"),
        python_version=raw.get("python_version"),
    )


def parse_system_status(raw: dict[str, Any]) -> tuple[FirmwareUpdate, ...]:
    """Parse get_system_status into one row per firmware component."""
    detail = (raw.get("updates") or {}).get("status_detail") or []
    return tuple(
        FirmwareUpdate(
            firmware_type=row.get("firmware_type", ""),
            state=row.get("state"),
            current_version=row.get("current_version"),
            target_version=row.get("target_version"),
            module_address=row.get("module_address"),
        )
        for row in detail
        if isinstance(row, dict)
    )


def parse_modules(raw: dict[str, Any]) -> dict[str, ModuleInfo]:
    """Parse get_modules_information.

    The response groups modules by source (`master`, `gateway`); the address is
    unique across those groups and is what the identifiers use (§4.1).
    """
    modules: dict[str, ModuleInfo] = {}
    for source, entries in (raw.get("modules") or {}).items():
        if not isinstance(entries, dict):
            continue
        for address, entry in entries.items():
            if not isinstance(entry, dict):
                continue
            modules[address] = ModuleInfo(
                address=address,
                source=source,
                module_type=entry.get("module_type", ""),
                hardware_type=entry.get("hardware_type", ""),
                online=bool(entry.get("online")),
                name=entry.get("name"),
                firmware_version=entry.get("firmware_version"),
                serial_number=entry.get("serial_number"),
            )
    return modules


def parse_plugins(raw: dict[str, Any]) -> dict[str, AppInfo]:
    """Parse get_plugins."""
    apps: dict[str, AppInfo] = {}
    for entry in raw.get("plugins") or []:
        if not isinstance(entry, dict) or not entry.get("name"):
            continue
        interfaces = tuple(
            pair[0]
            for pair in entry.get("interfaces") or []
            if isinstance(pair, (list, tuple)) and pair
        )
        apps[entry["name"]] = AppInfo(
            name=entry["name"],
            version=entry.get("version"),
            status=entry.get("status"),
            interfaces=interfaces,
        )
    return apps


# --- state -------------------------------------------------------------------


@dataclass(frozen=True)
class OutputState:
    """State of one output channel (§5.3)."""

    output_id: int
    on: bool
    locked: bool = False


def parse_output_status(raw: dict[str, Any]) -> dict[int, OutputState]:
    """Parse get_output_status.

    `dimmer` is deliberately dropped: all eight outputs report a constant 100,
    which carries no information (§2.3, correction 2).
    """
    outputs: dict[int, OutputState] = {}
    for entry in raw.get("status") or []:
        output_id = as_int(entry.get("id")) if isinstance(entry, dict) else None
        if output_id is None:
            continue
        outputs[output_id] = OutputState(
            output_id=output_id,
            on=bool(entry.get("status")),
            locked=bool(entry.get("locked")),
        )
    return outputs


def parse_input_status(raw: dict[str, Any]) -> dict[int, bool]:
    """Parse get_input_status — the dry contacts of the Brain (D-07)."""
    inputs: dict[int, bool] = {}
    for entry in raw.get("status") or []:
        input_id = as_int(entry.get("id")) if isinstance(entry, dict) else None
        if input_id is None:
            continue
        inputs[input_id] = bool(entry.get("status"))
    return inputs


# --- thermostat --------------------------------------------------------------


@dataclass(frozen=True)
class ThermostatState:
    """One OpenMotics thermostat, read over L2 (§5.4)."""

    thermostat_id: int
    group_id: int
    group_mode: str | None
    actual_temperature: float | None
    setpoint: float | None
    preset: str | None
    state: str | None
    steering_power: int | None
    output0: int | None = None
    output1: int | None = None
    hysteresis_active: bool | None = None
    control_mode: str | None = None
    overrule_setpoint: float | None = None
    overrule_reason: str | None = None
    overrule_source: str | None = None


def parse_thermostat_status(raw: dict[str, Any]) -> dict[int, ThermostatState]:
    """Parse get_thermostat_group_status.

    A group counts as active as soon as its `thermostats` list is not empty —
    the number of slots says nothing (V-12).
    """
    thermostats: dict[int, ThermostatState] = {}
    for group in raw.get("status") or []:
        if not isinstance(group, dict):
            continue
        group_id = as_int(group.get("id"))
        for entry in group.get("thermostats") or []:
            if not isinstance(entry, dict):
                continue
            thermostat_id = as_int(entry.get("id"))
            if thermostat_id is None or group_id is None:
                continue
            overrule = entry.get("overrule") or {}
            thermostats[thermostat_id] = ThermostatState(
                thermostat_id=thermostat_id,
                group_id=group_id,
                group_mode=group.get("mode"),
                actual_temperature=as_float(entry.get("actual_temperature")),
                setpoint=as_float(entry.get("setpoint_temperature")),
                preset=entry.get("preset"),
                state=entry.get("state"),
                steering_power=as_int(entry.get("steering_power")),
                output0=as_int(entry.get("output0")),
                output1=as_int(entry.get("output1")),
                hysteresis_active=entry.get("hysteresis_active"),
                control_mode=entry.get("control_mode"),
                overrule_setpoint=as_float(overrule.get("setpoint")),
                overrule_reason=overrule.get("reason"),
                overrule_source=overrule.get("source"),
            )
    return thermostats


# --- app configuration -------------------------------------------------------


@dataclass(frozen=True)
class LogicConfig:
    """The parts of `rensonheatpumplogic`'s configuration we expose (§5.6)."""

    silent_mode: bool | None = None
    silent_mode_recurrent: bool | None = None
    silent_mode_start_hour: str | None = None
    silent_max_time: float | None = None
    current_running_time: float | None = None
    backup_heater: bool | None = None
    type_energy_source: str | None = None
    three_way_valve_polarity: str | None = None
    heating_restart_difference: float | None = None
    warranty_number: str | None = None
    heatpump_name: str | None = None
    heatpump_modbus_address: int | None = None
    state: str | None = None
    commissioning_state: str | None = None
    hysteresis_top_zone0: float | None = None
    hysteresis_bottom_zone0: float | None = None
    hysteresis_top_zone1: float | None = None
    hysteresis_bottom_zone1: float | None = None
    energybus_address: str | None = None
    # hvac_config key → channel id, the wiring map of the installation (§2.3)
    channel_functions: dict[str, int] = field(default_factory=dict)


def parse_logic_config(raw: dict[str, Any]) -> LogicConfig:
    """Parse plugins/rensonheatpumplogic/get_config."""
    silent = _first(raw.get("silent_mode_config"))
    heatpump = _first(raw.get("heatpump_config"))
    state = _first(raw.get("state_config"))
    zone = _first(raw.get("zone_config"))
    hvac = _first(raw.get("hvac_config"))

    functions: dict[str, int] = {}
    for key, value in hvac.items():
        channel_id = as_int(value)
        if channel_id is not None:
            functions[key] = channel_id

    return LogicConfig(
        silent_mode=on_off(silent.get("silent_mode")),
        silent_mode_recurrent=on_off(silent.get("silent_mode_recurrent")),
        silent_mode_start_hour=silent.get("silent_mode_start_hour"),
        silent_max_time=as_float(silent.get("silent_max_time")),
        current_running_time=as_float(silent.get("current_running_time")),
        backup_heater=on_off(heatpump.get("backup_heater")),
        type_energy_source=heatpump.get("type_energy_source"),
        three_way_valve_polarity=heatpump.get("three_way_valve_polarity"),
        heating_restart_difference=as_float(heatpump.get("heating_restart_difference")),
        warranty_number=heatpump.get("warranty_number"),
        heatpump_name=heatpump.get("name"),
        heatpump_modbus_address=as_int(heatpump.get("modbus_address")),
        state=state.get("state"),
        commissioning_state=state.get("commissioning_state"),
        hysteresis_top_zone0=as_float(zone.get("hysteresis_top_zone0")),
        hysteresis_bottom_zone0=as_float(zone.get("hysteresis_bottom_zone0")),
        hysteresis_top_zone1=as_float(zone.get("hysteresis_top_zone1")),
        hysteresis_bottom_zone1=as_float(zone.get("hysteresis_bottom_zone1")),
        energybus_address=hvac.get("energybus_address"),
        channel_functions=functions,
    )


@dataclass(frozen=True)
class ThermostatAppConfig:
    """The configuration of `RensonThermostat` (§5.5)."""

    poll_interval: int | None = None
    modbus_backend: str | None = None
    manual_override_expiry: int | None = None
    update_thermostats: str | None = None
    # OpenMotics thermostat id → Modbus slave address
    bindings: dict[int, int] = field(default_factory=dict)
    # OpenMotics thermostat id → temperature offset
    offsets: dict[int, float] = field(default_factory=dict)


def parse_thermostat_app_config(raw: dict[str, Any]) -> ThermostatAppConfig:
    """Parse plugins/RensonThermostat/get_config."""
    bindings: dict[int, int] = {}
    offsets: dict[int, float] = {}
    for entry in raw.get("thermostats") or []:
        if not isinstance(entry, dict):
            continue
        thermostat_id = as_int(entry.get("thermostat_id"))
        address = as_int(entry.get("address"))
        if thermostat_id is None:
            continue
        if address is not None:
            bindings[thermostat_id] = address
        offset = as_float(entry.get("temp_offset"))
        if offset is not None:
            offsets[thermostat_id] = offset

    return ThermostatAppConfig(
        poll_interval=as_int(raw.get("poll_interval")),
        modbus_backend=raw.get("modbus_backend"),
        manual_override_expiry=as_int(raw.get("manual_override_expiry")),
        update_thermostats=raw.get("update_thermostats"),
        bindings=bindings,
        offsets=offsets,
    )


@dataclass(frozen=True)
class HeatPumpAppConfig:
    """The configuration of `RensonHeatPumpR290` (§5.7)."""

    device_name: str | None = None
    modbus_address: int | None = None


def parse_heatpump_app_config(raw: dict[str, Any]) -> HeatPumpAppConfig:
    """Parse plugins/RensonHeatPumpR290/get_config."""
    devices = raw.get("devices") or []
    device = devices[0] if devices and isinstance(devices[0], dict) else {}
    return HeatPumpAppConfig(
        device_name=device.get("name"),
        modbus_address=as_int(device.get("address")),
    )
