"""Binary sensors: the HVAC outputs, module presence and source health."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory

from .const import (
    APP_HEATPUMP,
    APP_LOGIC,
    HEATPUMP_ARRAYS,
    HVAC_MODULE_MODEL,
    HVAC_OUTPUTS,
    SOURCE_GATEWAY_CORE,
    SOURCE_HARDWARE_HEATPUMP,
    source_app_config,
    source_app_runtime,
)
from .entity import RensonChannelEntity, RensonEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import RensonConfigEntry, RensonRuntime
    from .const import Origin
    from .coordinators import RensonCoordinator


class RensonBinarySensor(RensonEntity, BinarySensorEntity):
    """A binary sensor whose value and availability are supplied as callables."""

    _entity_domain = "binary_sensor"

    def __init__(
        self,
        coordinator: RensonCoordinator,
        device: DeviceInfo,
        origin: Origin,
        key: str,
        name: str,
        source: str,
        is_on_fn: Callable[[Any], bool | None],
        endpoint: str | None = None,
        device_class: BinarySensorDeviceClass | None = None,
        entity_category: EntityCategory | None = None,
        enabled_default: bool = True,
        attributes_fn: Callable[[Any], dict[str, Any]] | None = None,
    ) -> None:
        """Bind the sensor to its source."""
        super().__init__(coordinator, device, origin, key, name, source, endpoint)
        self._is_on_fn = is_on_fn
        self._attributes_fn = attributes_fn
        self._attr_device_class = device_class
        self._attr_entity_category = entity_category
        self._attr_entity_registry_enabled_default = enabled_default

    @property
    def is_on(self) -> bool | None:
        """The current state, or None when the source has nothing to say."""
        return self._is_on_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Unavailable as soon as the source is — never a frozen value (§5.0)."""
        return super().available and self.is_on is not None

    def _extra_attributes(self) -> dict[str, Any]:
        return self._attributes_fn(self.coordinator.data) if self._attributes_fn else {}


class HvacOutputBinarySensor(RensonChannelEntity, BinarySensorEntity):
    """One output channel of the HVAC module (§5.3).

    The state comes from the gateway, so it keeps working when every Renson app
    stops; only the function label depends on `hvac_config` (§5.0).
    """

    _entity_domain = "binary_sensor"

    def __init__(self, coordinator, device, origin, channel, address, output_id):
        """Bind the sensor to one output."""
        super().__init__(
            coordinator,
            device,
            origin,
            channel,
            HVAC_MODULE_MODEL,
            address,
            SOURCE_GATEWAY_CORE,
            "get_output_status",
        )
        self._output_id = output_id
        if channel.diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = channel.enabled_default

    @property
    def is_on(self) -> bool | None:
        """The switching state of the channel."""
        state = self.coordinator.data.outputs.get(self._output_id)
        return state.on if state else None

    @property
    def available(self) -> bool:
        """Available while the gateway reports this output."""
        return super().available and self._output_id in self.coordinator.data.outputs

    def _extra_attributes(self) -> dict[str, Any]:
        attributes = super()._extra_attributes()
        state = self.coordinator.data.outputs.get(self._output_id)
        if state is not None:
            attributes["raw_value"] = int(state.on)
            attributes["locked"] = state.locked
        return attributes


def _app_entities(
    runtime: RensonRuntime, app: str, device: DeviceInfo, origin: Origin
) -> list[RensonBinarySensor]:
    """The two entities every app device gets (§5.5–5.7)."""
    return [
        RensonBinarySensor(
            runtime.topology,
            device,
            origin,
            "running",
            "App actief",
            source_app_runtime(app),
            lambda data, app=app: (
                data.apps[app].running if data and app in data.apps else None
            ),
            endpoint="get_plugins",
            device_class=BinarySensorDeviceClass.RUNNING,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        RensonBinarySensor(
            runtime.config,
            device,
            origin,
            # A PROBLEM sensor already reads OK/Probleem in Home Assistant, so the
            # name is the subject only: "Brondata: OK" (I-13).
            "source_problem",
            "Brondata",
            source_app_config(app),
            lambda data, app=app: not (data and app in data.raw),
            endpoint="get_config",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            attributes_fn=lambda _data, app=app: _health_attributes(runtime, app),
        ),
    ]


def _health_attributes(runtime: RensonRuntime, app: str) -> dict[str, Any]:
    """Why a source is failing, straight from the health tracker (§7.2)."""
    state = runtime.health.states.get(source_app_config(app))
    if state is None:
        return {}
    return {"status": state.status, "reason": state.reason}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RensonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    runtime = entry.runtime_data
    devices = runtime.devices
    entities: list[BinarySensorEntity] = []

    if devices.hvac is not None:
        for output_id, channel in HVAC_OUTPUTS.items():
            entities.append(
                HvacOutputBinarySensor(
                    runtime.state,
                    devices.hvac,
                    devices.hvac_origin,
                    channel,
                    devices.hvac_address,
                    output_id,
                )
            )
        entities.append(
            RensonBinarySensor(
                runtime.topology,
                devices.hvac,
                devices.hvac_origin,
                "module_present",
                "Module aanwezig",
                SOURCE_GATEWAY_CORE,
                lambda data: (
                    data.modules[devices.hvac_address].online
                    if data and devices.hvac_address in data.modules
                    else False
                ),
                endpoint="get_modules_information",
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        )

    # The Brain's own inputs. They are exposed for completeness (D-07) but are
    # off by default: in the reference configuration nothing is wired to them.
    for input_id in sorted(runtime.state.data.brain_inputs):
        entities.append(
            RensonBinarySensor(
                runtime.state,
                devices.brain,
                devices.brain_origin,
                f"input_{input_id}",
                f"Ingang {input_id + 1}",
                SOURCE_GATEWAY_CORE,
                lambda data, i=input_id: data.brain_inputs.get(i),
                endpoint="get_input_status",
                entity_category=EntityCategory.DIAGNOSTIC,
                enabled_default=False,
            )
        )

    for app, (device, origin) in devices.apps.items():
        entities.extend(_app_entities(runtime, app, device, origin))

    if devices.heatpump is not None:
        entities.append(
            RensonBinarySensor(
                runtime.state,
                devices.heatpump,
                devices.heatpump_origin,
                "reachable",
                "Warmtepomp bereikbaar",
                SOURCE_HARDWARE_HEATPUMP,
                lambda data: data.heatpump_reachable,
                endpoint="get_plugin_logs",
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                attributes_fn=_heatpump_attributes,
            )
        )

    for om_id, (device, origin) in devices.thermostats.items():
        entities.append(
            RensonBinarySensor(
                runtime.thermostat,
                device,
                origin,
                "reachable",
                "Thermostaat bereikbaar",
                SOURCE_GATEWAY_CORE,
                lambda data, i=om_id: bool(data and i in data),
                endpoint="get_thermostat_group_status",
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                entity_category=EntityCategory.DIAGNOSTIC,
                attributes_fn=_layer_l2,
            )
        )
        # An on/off flag of this thermostat, not its working state: it stayed ON
        # for two hours while the heat demand flipped three times (§5.4).
        entities.append(
            RensonBinarySensor(
                runtime.thermostat,
                device,
                origin,
                "enabled",
                "Thermostaat ingeschakeld",
                SOURCE_GATEWAY_CORE,
                lambda data, i=om_id: (
                    _on_off_state(data[i].state) if data and i in data else None
                ),
                endpoint="get_thermostat_group_status",
                device_class=BinarySensorDeviceClass.RUNNING,
                entity_category=EntityCategory.DIAGNOSTIC,
                attributes_fn=_layer_l2,
            )
        )
        # The controller belongs to `rensonheatpumplogic`, which syncs its
        # hysteresis config into the gateway; the Brain only executes it and is
        # the fallback without the app (I-16, P-06). The origin stays the
        # thermostat's (D-15).
        entities.append(
            RensonBinarySensor(
                runtime.thermostat,
                devices.apps.get(APP_LOGIC, (devices.brain, None))[0],
                origin,
                "hysteresis_active",
                f"Hysterese actief — thermostaat {om_id}",
                SOURCE_GATEWAY_CORE,
                lambda data, i=om_id: (
                    data[i].hysteresis_active if data and i in data else None
                ),
                endpoint="get_thermostat_group_status",
                entity_category=EntityCategory.DIAGNOSTIC,
                attributes_fn=_layer_l2,
            )
        )

    if APP_LOGIC in devices.apps:
        device, origin = devices.apps[APP_LOGIC]
        for key, name, field in (
            ("silent_mode", "Stille modus actief", "silent_mode"),
            (
                "silent_mode_recurrent",
                "Stille modus terugkerend",
                "silent_mode_recurrent",
            ),
            ("backup_heater", "Backup heater ingeschakeld", "backup_heater"),
        ):
            entities.append(
                RensonBinarySensor(
                    runtime.config,
                    device,
                    origin,
                    key,
                    name,
                    source_app_config(APP_LOGIC),
                    lambda data, f=field: (
                        getattr(data.logic, f) if data and data.logic else None
                    ),
                    endpoint="get_config",
                    entity_category=(
                        EntityCategory.DIAGNOSTIC
                        if key == "silent_mode_recurrent"
                        else None
                    ),
                )
            )

    async_add_entities(entities)


def _layer_l2(_data) -> dict[str, Any]:
    """The OpenMotics layer of the thermostat model (§5.4)."""
    return {"layer": "L2"}


def _on_off_state(state: str | None) -> bool | None:
    if state == "ON":
        return True
    if state == "OFF":
        return False
    return None


def _heatpump_attributes(data) -> dict[str, Any]:
    """The evidence behind the state, and what the driver app says about itself.

    The `Could not enable Modbus` text stays readable here as a reason, never as
    the state: the app that logs it has no Modbus configured at all (§5.7).
    """
    attributes: dict[str, Any] = {
        "last_seen": data.heatpump_seen.isoformat() if data.heatpump_seen else None,
        "evidence": " of ".join(HEATPUMP_ARRAYS),
    }
    health = data.app_health.get(APP_HEATPUMP)
    if health is not None:
        attributes["driver_reason"] = health.reason
        attributes["watchdog_restarts"] = health.watchdog_restarts
    return attributes
