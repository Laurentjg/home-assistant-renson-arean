"""DeviceInfo factories — the topology of §4 in exactly one place.

Every identifier roots on the config entry's `entry_id` (D-13). The gateway has
no serial number and no other stable hardware id (V-17), and of the candidates
only `entry_id` fails at a moment the user causes themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    APP_HEATPUMP,
    APP_MODELS,
    BRAIN_MODULE_MODEL,
    DOMAIN,
    HEATPUMP_MODEL,
    HVAC_MODULE_MODEL,
    CONNECTED_TO_HVAC,
    HEATPUMP_SLAVE,
    MANUFACTURER,
    app_id,
    brain_id,
    heatpump_id,
    module_id,
    thermostat_id,
)

if TYPE_CHECKING:
    from .api.models import Topology


def brain_device(
    entry_id: str, host: str, gateway: str | None, master: str | None
) -> DeviceInfo:
    """The Brain module. It is the hub; there is no device above it (D-01)."""
    return DeviceInfo(
        identifiers={(DOMAIN, brain_id(entry_id))},
        manufacturer=MANUFACTURER,
        name="Brain module",
        model=BRAIN_MODULE_MODEL,
        sw_version=gateway,
        hw_version=master,
        configuration_url=f"https://{host}",
    )


def hvac_module_device(
    entry_id: str, address: str, firmware: str | None, serial: str | None
) -> DeviceInfo:
    """The HVAC module — the only box with power outputs and sensor inputs."""
    return DeviceInfo(
        identifiers={(DOMAIN, module_id(entry_id, address))},
        via_device=(DOMAIN, brain_id(entry_id)),
        manufacturer=MANUFACTURER,
        name="HVAC module",
        model=HVAC_MODULE_MODEL,
        sw_version=firmware,
        serial_number=serial,
    )


def thermostat_device(
    entry_id: str, om_id: int, slave: int | None, via: str
) -> DeviceInfo:
    """One wall thermostat. `via` is the identifier of the device it hangs on.

    Whether that is the Brain or the HVAC module is not derivable from the API
    (V-13), so it is an option rather than an assumption.
    """
    model = (
        f"Wandthermostaat (Modbus {slave})"
        if slave is not None
        else "OpenMotics-thermostaat"
    )
    return DeviceInfo(
        identifiers={(DOMAIN, thermostat_id(entry_id, om_id))},
        via_device=(DOMAIN, via),
        manufacturer=MANUFACTURER,
        name=f"Thermostaat {om_id}",
        model=model,
    )


def app_device(entry_id: str, app: str, version: str | None) -> DeviceInfo:
    """A Brain app.

    The technical name is the name; the readable one goes in the model (D-05),
    so looking it up in OpenMotics stays trivial.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, app_id(entry_id, app))},
        via_device=(DOMAIN, brain_id(entry_id)),
        manufacturer=MANUFACTURER,
        name=f"Brain-App {app}",
        model=APP_MODELS.get(app, "Brain-app"),
        sw_version=version,
    )


def heatpump_device(entry_id: str, app: str, slave: int) -> DeviceInfo:
    """The heat pump itself. Always present (D-02)."""
    return DeviceInfo(
        identifiers={(DOMAIN, heatpump_id(entry_id, slave))},
        via_device=(DOMAIN, app_id(entry_id, app)),
        manufacturer=MANUFACTURER,
        name="Renson Arean R290",
        model=HEATPUMP_MODEL,
    )


@dataclass(frozen=True)
class DeviceSet:
    """Every device of one config entry, built once and shared by the platforms.

    Keeping this in one place is the point of §4: the topology is described
    exactly here and nowhere else.
    """

    brain: DeviceInfo
    brain_identifier: str
    apps: dict[str, tuple[DeviceInfo, str]] = field(default_factory=dict)
    thermostats: dict[int, tuple[DeviceInfo, str]] = field(default_factory=dict)
    hvac: DeviceInfo | None = None
    hvac_identifier: str | None = None
    hvac_address: str | None = None
    heatpump: DeviceInfo | None = None
    heatpump_identifier: str | None = None


def build_devices(
    entry_id: str,
    host: str,
    topology: Topology,
    thermostats: dict[int, Any],
    bindings: dict[int, int],
    connected_to: str,
) -> DeviceSet:
    """Derive the device tree from what the gateway currently reports (P-05)."""
    brain = brain_device(
        entry_id, host, topology.version.gateway, topology.version.master
    )

    hvac_info: DeviceInfo | None = None
    hvac_identifier: str | None = None
    hvac_address: str | None = None
    module = topology.hvac_module
    if module is not None:
        hvac_address = module.address
        hvac_identifier = module_id(entry_id, module.address)
        hvac_info = hvac_module_device(
            entry_id, module.address, module.firmware_version, module.serial_number
        )

    apps = {
        name: (app_device(entry_id, name, info.version), app_id(entry_id, name))
        for name, info in topology.apps.items()
    }

    via = (
        hvac_identifier
        if connected_to == CONNECTED_TO_HVAC and hvac_identifier
        else brain_id(entry_id)
    )
    thermostat_devices = {
        om_id: (
            thermostat_device(entry_id, om_id, bindings.get(om_id), via),
            thermostat_id(entry_id, om_id),
        )
        for om_id in thermostats
    }

    # The heat pump always exists, whatever the log yields (D-02).
    heatpump_info: DeviceInfo | None = None
    heatpump_identifier: str | None = None
    if APP_HEATPUMP in topology.apps:
        heatpump_info = heatpump_device(entry_id, APP_HEATPUMP, HEATPUMP_SLAVE)
        heatpump_identifier = heatpump_id(entry_id, HEATPUMP_SLAVE)

    return DeviceSet(
        brain=brain,
        brain_identifier=brain_id(entry_id),
        apps=apps,
        thermostats=thermostat_devices,
        hvac=hvac_info,
        hvac_identifier=hvac_identifier,
        hvac_address=hvac_address,
        heatpump=heatpump_info,
        heatpump_identifier=heatpump_identifier,
    )
