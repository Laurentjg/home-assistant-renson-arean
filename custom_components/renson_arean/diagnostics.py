"""Diagnostics for the Renson Arean integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry

from .const import CONF_PASSWORD, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import RensonCoordinator

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: RensonCoordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "data": {
            "thermostat_status": coordinator.data.thermostat_status.__dict__,
            "outputs": {
                oid: o.__dict__ for oid, o in coordinator.data.outputs.items()
            },
            "silent_mode": coordinator.data.silent_mode,
            "gateway_serial": coordinator.data.gateway_serial,
        },
    }
