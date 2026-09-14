"""Diagnostics.

Everything that could identify or authenticate is redacted (M-02). The token is
never on disk to begin with (M-01), and the password lives in the URL of the
login call, so a naive dump would leak it (M-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import RensonConfigEntry

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_HOST,
    "token",
    "serial",
    "serial_number",
    "warranty_number",
    "latitude",
    "longitude",
    "postal_code",
    "city_name",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RensonConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for one config entry."""
    runtime = entry.runtime_data
    topology = runtime.topology.data
    state = runtime.state.data

    return async_redact_data(
        {
            "entry": {"data": dict(entry.data), "options": dict(entry.options)},
            "versions": {
                "gateway": topology.version.gateway if topology else None,
                "master": topology.version.master if topology else None,
                "apps": {
                    name: {"version": app.version, "status": app.status}
                    for name, app in (topology.apps.items() if topology else ())
                },
            },
            "modules": {
                address: {
                    "type": module.module_type,
                    "hardware_type": module.hardware_type,
                    "firmware_version": module.firmware_version,
                    "online": module.online,
                    "serial_number": module.serial_number,
                }
                for address, module in (topology.modules.items() if topology else ())
            },
            "sources": {
                source: {"status": item.status, "reason": item.reason}
                for source, item in runtime.health.states.items()
            },
            "ssr": {
                "arrays": dict(state.ssr.arrays) if state else {},
                "rejected": list(state.ssr.rejected) if state else [],
                # Arrays the table does not know yet — candidates for V-16 (I-19).
                "unknown": list(state.ssr.unknown) if state else [],
            },
            "config": dict(runtime.config.data.raw) if runtime.config.data else {},
        },
        TO_REDACT,
    )
