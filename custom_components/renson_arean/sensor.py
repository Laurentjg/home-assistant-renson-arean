"""Sensors.

Three groups live here, and they behave very differently when something fails
(§5.0): gateway values keep working whatever the apps do, app configuration
disappears with its app, and the log-derived values disappear with the app *or*
when it changes its log format (D-14).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory

from .const import (
    APP_HEATPUMP,
    APP_LOGIC,
    APP_THERMOSTAT,
    CONFIDENCE_ASSUMED,
    HEATPUMP_ARRAYS,
    HVAC_INPUTS,
    HVAC_OUTPUTS,
    OM_PRESET_TO_HA,
    SOURCE_GATEWAY_CORE,
    SSR_APP_VERSION,
    SSR_ARRAYS,
    SUBSYSTEM_DHW,
    SUBSYSTEM_RECIRCULATION,
    source_app_config,
    source_app_log,
)
from .entity import RensonEntity, entity_id_for

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import RensonConfigEntry, RensonRuntime
    from .const import HvacChannel, Origin, SsrArray, SsrPosition
    from .coordinators import RensonCoordinator

DIAGNOSTIC = EntityCategory.DIAGNOSTIC


class RensonSensor(RensonEntity, SensorEntity):
    """A sensor whose value is supplied as a callable over its coordinator data."""

    _entity_domain = "sensor"

    def __init__(
        self,
        coordinator: RensonCoordinator,
        device: DeviceInfo,
        origin: Origin,
        key: str,
        name: str,
        source: str,
        value_fn: Callable[[Any], Any],
        endpoint: str | None = None,
        device_class: SensorDeviceClass | None = None,
        unit: str | None = None,
        entity_category: EntityCategory | None = None,
        enabled_default: bool = True,
        attributes_fn: Callable[[Any], dict[str, Any]] | None = None,
        state_class: SensorStateClass | None = None,
    ) -> None:
        """Bind the sensor to its source."""
        super().__init__(coordinator, device, origin, key, name, source, endpoint)
        self._value_fn = value_fn
        self._attributes_fn = attributes_fn
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit
        self._attr_entity_category = entity_category
        self._attr_entity_registry_enabled_default = enabled_default

    @property
    def native_value(self) -> Any:
        """The current value, or None while the source has nothing."""
        return self._value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Unavailable as soon as the source is (§5.0)."""
        return super().available and self.native_value is not None

    def _extra_attributes(self) -> dict[str, Any]:
        return self._attributes_fn(self.coordinator.data) if self._attributes_fn else {}


class SsrPositionSensor(RensonSensor):
    """One position of an SSR array, published under a neutral name.

    These exist so the meaning of the remaining positions can be established by
    correlation later (V-16). They interpret nothing: booleans are rendered as
    text, numbers pass through untouched, and the Modbus "not available"
    sentinel has already been turned into no value at all (S-01).

    An instrument, not user information: off by default. The name carries the
    meaning as far as it is known (§4.3, I-20); the entity_id stays physical.
    """

    def __init__(self, coordinator, device, origin, array: SsrArray, index: int):
        """Bind the sensor to one array position."""
        super().__init__(
            coordinator,
            device,
            origin,
            f"{array.slug}:{index + 1}",
            array.raw_name(index),
            source_app_log(APP_LOGIC),
            lambda data, key=array.key, i=index: _raw(data.ssr.value(key, i)),
            endpoint="get_plugin_logs",
            entity_category=DIAGNOSTIC,
            enabled_default=False,
            attributes_fn=lambda _data, a=array, i=index: _position_attributes(a, i),
        )


def _raw(value: Any) -> Any:
    """Render a raw array value without interpreting it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _position_attributes(array: SsrArray, index: int) -> dict[str, Any]:
    position = array.position(index)
    attributes: dict[str, Any] = {"array": array.key, "position": index + 1}
    if position is not None:
        attributes["mapped_to"] = position.name
        attributes["function_confidence"] = position.confidence
    else:
        attributes["mapped_to"] = None
        attributes["function_confidence"] = "unknown"
    return attributes


def _ssr_sensor(
    runtime: RensonRuntime,
    device: DeviceInfo,
    origin: Origin,
    array_key: str,
    position: SsrPosition,
    requires_heatpump: bool = False,
) -> RensonSensor:
    """A named sensor fed by one SSR position.

    `requires_heatpump` makes the value disappear together with
    `hardware:heatpump`, so a monobloc outage shows as one recognisable event
    across the whole device rather than position by position (§5.0).
    """
    return RensonSensor(
        runtime.state,
        device,
        origin,
        position.key,
        position.name,
        source_app_log(APP_LOGIC),
        lambda data, k=array_key, i=position.index, r=requires_heatpump: (
            data.ssr.value(k, i) if data.heatpump_reachable or not r else None
        ),
        endpoint="get_plugin_logs",
        device_class=(
            SensorDeviceClass(position.device_class) if position.device_class else None
        ),
        unit=position.unit,
        state_class=(
            SensorStateClass(position.state_class) if position.state_class else None
        ),
        entity_category=DIAGNOSTIC if position.diagnostic else None,
        attributes_fn=lambda _data, p=position, k=array_key: {
            "function_confidence": p.confidence,
            "array": k,
            "position": p.index + 1,
            "verification": (
                "te controleren, zie non-public/design/open-issues.md"
                if p.confidence == CONFIDENCE_ASSUMED
                else None
            ),
        },
    )


def _brain_sensors(runtime: RensonRuntime) -> list[RensonSensor]:
    devices = runtime.devices
    device, origin = devices.brain, devices.brain_origin
    return [
        RensonSensor(
            runtime.topology,
            device,
            origin,
            "gateway_version",
            "Firmwareversie",
            SOURCE_GATEWAY_CORE,
            lambda data: data.version.gateway if data else None,
            endpoint="get_version",
            entity_category=DIAGNOSTIC,
            enabled_default=False,
        ),
        RensonSensor(
            runtime.topology,
            device,
            origin,
            "master_version",
            "Masterversie",
            SOURCE_GATEWAY_CORE,
            lambda data: data.version.master if data else None,
            endpoint="get_version",
            entity_category=DIAGNOSTIC,
            enabled_default=False,
        ),
        RensonSensor(
            runtime.topology,
            device,
            origin,
            "updates_available",
            "Update beschikbaar",
            SOURCE_GATEWAY_CORE,
            lambda data: (
                sum(1 for u in data.updates if u.update_available) if data else None
            ),
            endpoint="get_system_status",
            entity_category=DIAGNOSTIC,
            attributes_fn=lambda data: {
                "components": [
                    {
                        "firmware_type": update.firmware_type,
                        "current_version": update.current_version,
                        "target_version": update.target_version,
                        "state": update.state,
                    }
                    for update in (data.updates if data else ())
                ]
            },
        ),
        # The state is the number of *missing* modules, so 0 means healthy and
        # the value is usable in an alarm; the list is in the attributes (§5.2).
        RensonSensor(
            runtime.topology,
            device,
            origin,
            "system_bus",
            "Systeembus",
            SOURCE_GATEWAY_CORE,
            lambda data: len(data.offline_modules) if data else None,
            endpoint="get_modules_information",
            entity_category=DIAGNOSTIC,
            attributes_fn=lambda data: {
                "modules": [
                    {
                        "address": module.address,
                        "type": module.module_type,
                        "hardware": module.hardware_type,
                        "firmware": module.firmware_version,
                        "online": module.online,
                    }
                    for module in (data.modules.values() if data else ())
                ]
            },
        ),
    ]


def _channel_overview(runtime: RensonRuntime) -> RensonSensor:
    """One diagnostic sensor holding the whole channel map (§4.3).

    The state is the number of wired channels; the attributes are the table
    that tells the person at the fuse box which channel is which — and, just as
    important, which source each one hangs on, so half a device going quiet is
    explainable at a glance.
    """
    devices = runtime.devices
    rows: list[dict[str, Any]] = []
    for output_id, channel in HVAC_OUTPUTS.items():
        rows.append(
            {
                "channel": channel.channel,
                "direction": channel.direction,
                "id": output_id,
                "function": channel.default_name,
                "source": SOURCE_GATEWAY_CORE,
                "entity": entity_id_for(
                    "binary_sensor", devices.hvac_origin, channel.key
                ),
                "wired": channel.wired,
            }
        )
    for input_id, channel in HVAC_INPUTS.items():
        position = _input_position(channel.key)
        key = position.key if position else _unmapped_input_key(channel)
        rows.append(
            {
                "channel": channel.channel,
                "direction": channel.direction,
                "id": input_id,
                "function": channel.default_name,
                "source": source_app_log(APP_LOGIC),
                "entity": (
                    entity_id_for("sensor", devices.hvac_origin, key) if key else None
                ),
                "wired": channel.wired,
            }
        )
        if position is None and key is not None:
            rows[-1]["no_value_reason"] = (
                f"geen arraypositie vastgesteld voor app-versie {SSR_APP_VERSION}"
            )

    wired = sum(1 for row in rows if row["wired"] == "true")
    return RensonSensor(
        runtime.state,
        devices.hvac,
        devices.hvac_origin,
        "channel_overview",
        "Kanaaloverzicht",
        SOURCE_GATEWAY_CORE,
        lambda _data, count=wired: count,
        entity_category=DIAGNOSTIC,
        attributes_fn=lambda _data, rows=rows: {"channels": rows},
    )


def _input_position(channel_key: str) -> SsrPosition | None:
    """The SSR position that feeds one HVAC input, if one is established.

    An analog input has both a voltage and a pressure position; the pressure is
    the one the user reads, so it wins.
    """
    positions = [
        position
        for position in SSR_ARRAYS["HP_HVAC/0"].positions
        if position.entity and position.key.startswith(channel_key)
    ]
    for position in positions:
        if not position.diagnostic:
            return position
    return positions[0] if positions else None


def _unmapped_input_key(channel: HvacChannel) -> str | None:
    """The entity key of a temperature input without an array position (I-15)."""
    if channel.subsystem is None:
        return None
    return f"{channel.key}_temperature"


def _subsystem_in_use(runtime: RensonRuntime, subsystem: str) -> bool:
    """Whether the installation uses the subsystem behind an input.

    Read once at setup: it decides `enabled_default`, which only matters when
    the entity is first registered.
    """
    config = runtime.config.data
    logic = config.logic if config else None
    if logic is None:
        return False
    if subsystem == SUBSYSTEM_DHW:
        return logic.dhw_status not in (None, "Disabled")
    if subsystem == SUBSYSTEM_RECIRCULATION:
        return bool(logic.has_recirculation)
    return False


def _unmapped_input_sensors(runtime: RensonRuntime) -> list[RensonSensor]:
    """T1, T2 and T4: an entity that tells why it has no value (§5.3, I-15).

    HP_HVAC/0 has twelve positions and all twelve are taken, so there is
    nothing to read. The entity exists for installations whose array is longer,
    and stays unavailable rather than guessing. Why it has no value is stated in
    the channel overview: an unavailable entity publishes no attributes.
    """
    devices = runtime.devices
    sensors: list[RensonSensor] = []
    for channel in HVAC_INPUTS.values():
        key = _unmapped_input_key(channel)
        if key is None:
            continue
        sensors.append(
            RensonSensor(
                runtime.state,
                devices.hvac,
                devices.hvac_origin,
                key,
                channel.default_name,
                source_app_log(APP_LOGIC),
                lambda _data: None,
                endpoint="get_plugin_logs",
                device_class=SensorDeviceClass.TEMPERATURE,
                unit="°C",
                enabled_default=_subsystem_in_use(runtime, channel.subsystem),
            )
        )
    return sensors


def _thermostat_sensors(runtime: RensonRuntime) -> list[RensonSensor]:
    """The thermostat device carries what the user reads off the wall unit (§5.4).

    Steering power is `active_value` of the hysteresis config that
    `rensonheatpumplogic` syncs into the gateway thermostat: it is shown on that
    app — on the Brain, which only executes, when the app is absent (P-06) —
    under the thermostat's own origin, so its identity does not depend on where
    it is displayed (D-15, I-16).
    """
    sensors: list[RensonSensor] = []
    devices = runtime.devices
    controller = devices.apps.get(APP_LOGIC, (devices.brain, None))[0]
    for om_id, (device, origin) in devices.thermostats.items():
        for key, name, getter, device_class, unit, category, target, layer in (
            (
                "room_temperature",
                "Ruimtetemperatuur",
                lambda t: t.actual_temperature,
                SensorDeviceClass.TEMPERATURE,
                "°C",
                None,
                device,
                "L1",
            ),
            (
                "steering_power",
                f"Stuurvermogen — thermostaat {om_id}",
                lambda t: t.steering_power,
                None,
                "%",
                DIAGNOSTIC,
                controller,
                "L2",
            ),
            (
                "active_preset",
                "Actief preset",
                lambda t: OM_PRESET_TO_HA.get(t.preset or "", t.preset),
                None,
                None,
                DIAGNOSTIC,
                device,
                "L2",
            ),
        ):
            sensors.append(
                RensonSensor(
                    runtime.thermostat,
                    target,
                    origin,
                    key,
                    name,
                    SOURCE_GATEWAY_CORE,
                    lambda data, i=om_id, g=getter: (
                        g(data[i]) if data and i in data else None
                    ),
                    endpoint="get_thermostat_group_status",
                    device_class=device_class,
                    unit=unit,
                    entity_category=category,
                    attributes_fn=lambda _data, layer=layer: {"layer": layer},
                )
            )
    return sensors


def _logic_config_sensors(
    runtime: RensonRuntime, device: DeviceInfo, origin: Origin
) -> list[RensonSensor]:
    fields = (
        ("silent_start_hour", "Starttijd stille modus", "silent_mode_start_hour", None, True),
        ("silent_max_time", "Max. duur stille modus", "silent_max_time", "h", True),
        ("silent_running_time", "Looptijd stille modus", "current_running_time", "h", True),
        ("energy_source", "Energiebron", "type_energy_source", None, False),
        (
            "three_way_valve_polarity",
            "Driewegklep-polariteit",
            "three_way_valve_polarity",
            None,
            False,
        ),
        (
            "heating_restart_difference",
            "Heating restart difference",
            "heating_restart_difference",
            None,
            False,
        ),
        ("state", "Logica-state", "state", None, True),
        ("commissioning_state", "Commissioning state", "commissioning_state", None, True),
        ("hysteresis_top_zone0", "Hysterese boven zone 0", "hysteresis_top_zone0", "°C", False),
        (
            "hysteresis_bottom_zone0",
            "Hysterese onder zone 0",
            "hysteresis_bottom_zone0",
            "°C",
            False,
        ),
        ("hysteresis_top_zone1", "Hysterese boven zone 1", "hysteresis_top_zone1", "°C", False),
        (
            "hysteresis_bottom_zone1",
            "Hysterese onder zone 1",
            "hysteresis_bottom_zone1",
            "°C",
            False,
        ),
    )
    return [
        RensonSensor(
            runtime.config,
            device,
            origin,
            key,
            name,
            source_app_config(APP_LOGIC),
            lambda data, f=field: getattr(data.logic, f) if data and data.logic else None,
            endpoint="get_config",
            unit=unit,
            entity_category=DIAGNOSTIC,
            enabled_default=enabled,
        )
        for key, name, field, unit, enabled in fields
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RensonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    runtime = entry.runtime_data
    devices = runtime.devices
    entities: list[SensorEntity] = _brain_sensors(runtime)
    entities.extend(_thermostat_sensors(runtime))

    if devices.hvac is not None:
        entities.append(
            RensonSensor(
                runtime.topology,
                devices.hvac,
                devices.hvac_origin,
                "module_firmware",
                "Firmwareversie module",
                SOURCE_GATEWAY_CORE,
                lambda data: (
                    data.modules[devices.hvac_address].firmware_version
                    if data and devices.hvac_address in data.modules
                    else None
                ),
                endpoint="get_modules_information",
                entity_category=DIAGNOSTIC,
                enabled_default=False,
            )
        )
        entities.append(_channel_overview(runtime))
        for position in SSR_ARRAYS["HP_HVAC/0"].positions:
            if not position.entity:
                continue
            entities.append(
                _ssr_sensor(
                    runtime, devices.hvac, devices.hvac_origin, "HP_HVAC/0", position
                )
            )
        entities.extend(_unmapped_input_sensors(runtime))
        entities.append(
            RensonSensor(
                runtime.state,
                devices.hvac,
                devices.hvac_origin,
                "bypass_state",
                "Bypass-stand",
                source_app_log(APP_LOGIC),
                lambda data: data.ssr.bypass_state,
                endpoint="get_plugin_logs",
                entity_category=DIAGNOSTIC,
            )
        )

    if devices.heatpump is not None:
        for array_key in HEATPUMP_ARRAYS:
            for position in SSR_ARRAYS[array_key].positions:
                if not position.entity:
                    continue
                entities.append(
                    _ssr_sensor(
                        runtime,
                        devices.heatpump,
                        devices.heatpump_origin,
                        array_key,
                        position,
                        requires_heatpump=True,
                    )
                )
        entities.append(
            RensonSensor(
                runtime.state,
                devices.heatpump,
                devices.heatpump_origin,
                "outside_temperature",
                "Buitentemperatuur",
                source_app_log(APP_LOGIC),
                lambda data: (
                    data.ssr.weather_temperature if data.heatpump_reachable else None
                ),
                endpoint="get_plugin_logs",
                device_class=SensorDeviceClass.TEMPERATURE,
                unit="°C",
                state_class=SensorStateClass.MEASUREMENT,
                attributes_fn=lambda _data: {
                    "note": (
                        "De app haalt deze waarde zelf op; de integratie leest "
                        "hem uit het lokale log en belt niet naar buiten (E-01)."
                    )
                },
            )
        )
        entities.append(
            RensonSensor(
                runtime.config,
                devices.heatpump,
                devices.heatpump_origin,
                "warranty_number",
                "Garantienummer",
                source_app_config(APP_LOGIC),
                lambda data: (
                    (data.logic.warranty_number or None)
                    if data and data.logic
                    else None
                ),
                endpoint="get_config",
                entity_category=DIAGNOSTIC,
                enabled_default=False,
            )
        )

    for app, (device, origin) in devices.apps.items():
        entities.append(
            RensonSensor(
                runtime.topology,
                device,
                origin,
                "version",
                "App-versie",
                SOURCE_GATEWAY_CORE,
                lambda data, a=app: (
                    data.apps[a].version if data and a in data.apps else None
                ),
                endpoint="get_plugins",
                entity_category=DIAGNOSTIC,
                enabled_default=False,
            )
        )

    if APP_LOGIC in devices.apps:
        device, origin = devices.apps[APP_LOGIC]
        entities.extend(_logic_config_sensors(runtime, device, origin))
        # Every position of every array, under a neutral name, so the meaning of
        # the unmapped ones can be established by correlation later (V-16).
        for array in SSR_ARRAYS.values():
            for index in range(array.length):
                entities.append(
                    SsrPositionSensor(
                        runtime.state, device, devices.ssr_origin, array, index
                    )
                )

    if APP_THERMOSTAT in devices.apps:
        device, origin = devices.apps[APP_THERMOSTAT]
        for key, name, getter, unit in (
            ("poll_interval", "Poll-interval", lambda c: c.poll_interval, "s"),
            (
                "modbus_address",
                "Modbus-adres thermostaat",
                lambda c: next(iter(c.bindings.values()), None),
                None,
            ),
            (
                "temperature_offset",
                "Temperatuuroffset",
                lambda c: next(iter(c.offsets.values()), None),
                "°C",
            ),
            (
                "manual_override_expiry",
                "Manual override expiry",
                lambda c: c.manual_override_expiry,
                None,
            ),
        ):
            entities.append(
                RensonSensor(
                    runtime.config,
                    device,
                    origin,
                    key,
                    name,
                    source_app_config(APP_THERMOSTAT),
                    lambda data, g=getter: (
                        g(data.thermostat_app)
                        if data and data.thermostat_app
                        else None
                    ),
                    endpoint="get_config",
                    unit=unit,
                    entity_category=DIAGNOSTIC,
                    enabled_default=False,
                )
            )

    if APP_HEATPUMP in devices.apps:
        device, origin = devices.apps[APP_HEATPUMP]
        for key, name, getter in (
            ("modbus_address", "Modbus-adres warmtepomp", lambda c: c.modbus_address),
            ("device_name", "Naam Modbus-device", lambda c: c.device_name),
        ):
            entities.append(
                RensonSensor(
                    runtime.config,
                    device,
                    origin,
                    key,
                    name,
                    source_app_config(APP_HEATPUMP),
                    lambda data, g=getter: (
                        g(data.heatpump_app) if data and data.heatpump_app else None
                    ),
                    endpoint="get_config",
                    entity_category=DIAGNOSTIC,
                    enabled_default=False,
                )
            )

    async_add_entities(entities)
