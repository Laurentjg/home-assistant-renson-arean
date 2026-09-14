"""The Renson Arean integration — local access to the OpenMotics gateway.

This integration talks to the Renson Smart Living installation over the local
network only. It never uses the Renson cloud, the Renson One account or the
Renson One app (§1.1, P-08, E-01).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api.client import RensonAuthError, RensonClient, RensonError
from .const import (
    CONF_HOST,
    CONF_THERMOSTAT_CONNECTED_TO,
    CONF_INTERVAL_CONFIG,
    CONF_INTERVAL_STATE,
    CONF_INTERVAL_THERMOSTAT,
    CONF_INTERVAL_TOPOLOGY,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DEFAULT_INTERVAL_CONFIG,
    DEFAULT_INTERVAL_STATE,
    DEFAULT_INTERVAL_THERMOSTAT,
    DEFAULT_INTERVAL_TOPOLOGY,
    DEFAULT_CONNECTED_TO,
    DEFAULT_VERIFY_SSL,
    PLATFORMS,
)
from .coordinators.config import ConfigCoordinator
from .coordinators.state import StateCoordinator
from .coordinators.thermostat import ThermostatCoordinator
from .coordinators.topology import TopologyCoordinator
from .devices import DeviceSet, build_devices
from .health import SourceHealthTracker
from .thermostat.confirm import ConfirmationWindow

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass
class RensonRuntime:
    """Everything an entity needs, hung on the config entry."""

    client: RensonClient
    health: SourceHealthTracker
    topology: TopologyCoordinator
    thermostat: ThermostatCoordinator
    state: StateCoordinator
    config: ConfigCoordinator
    entry_id: str
    host: str
    connected_to: str
    # The device tree of §4, built once from what the gateway reports.
    devices: DeviceSet
    # One confirmation window per OpenMotics thermostat (§6.2).
    windows: dict[int, ConfirmationWindow]


type RensonConfigEntry = ConfigEntry[RensonRuntime]


def _interval(entry: ConfigEntry, key: str, default: timedelta) -> timedelta:
    seconds = entry.options.get(key)
    return timedelta(seconds=seconds) if seconds else default


async def async_setup_entry(hass: HomeAssistant, entry: RensonConfigEntry) -> bool:
    """Set up one gateway (§10.1)."""
    session = async_create_clientsession(
        hass, verify_ssl=entry.options.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
    )
    client = RensonClient(
        session,
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    try:
        await client.login()
    except RensonAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except RensonError as err:
        raise ConfigEntryNotReady(str(err)) from err

    health = SourceHealthTracker()

    topology = TopologyCoordinator(
        hass,
        client,
        health,
        _interval(entry, CONF_INTERVAL_TOPOLOGY, DEFAULT_INTERVAL_TOPOLOGY),
    )
    await topology.async_config_entry_first_refresh()

    thermostat = ThermostatCoordinator(
        hass,
        client,
        health,
        "thermostat",
        _interval(entry, CONF_INTERVAL_THERMOSTAT, DEFAULT_INTERVAL_THERMOSTAT),
    )
    state = StateCoordinator(
        hass,
        client,
        health,
        _interval(entry, CONF_INTERVAL_STATE, DEFAULT_INTERVAL_STATE),
        app_version=topology.app_version,
    )
    config = ConfigCoordinator(
        hass,
        client,
        health,
        _interval(entry, CONF_INTERVAL_CONFIG, DEFAULT_INTERVAL_CONFIG),
        apps=lambda: list(topology.data.apps) if topology.data else [],
    )

    for coordinator in (thermostat, state, config):
        await coordinator.async_config_entry_first_refresh()

    # One line per source, so the start of the log is the complete picture (§7.2).
    health.log_startup_summary()

    connected_to = entry.options.get(
        CONF_THERMOSTAT_CONNECTED_TO, DEFAULT_CONNECTED_TO
    )
    bindings = (
        config.data.thermostat_app.bindings
        if config.data and config.data.thermostat_app
        else {}
    )
    devices = build_devices(
        entry.entry_id,
        entry.data[CONF_HOST],
        topology.data,
        thermostat.data or {},
        bindings,
        connected_to,
    )

    entry.runtime_data = RensonRuntime(
        client=client,
        health=health,
        topology=topology,
        thermostat=thermostat,
        state=state,
        config=config,
        entry_id=entry.entry_id,
        host=entry.data[CONF_HOST],
        connected_to=connected_to,
        devices=devices,
        windows={},
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RensonConfigEntry) -> bool:
    """Unload the config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload so new intervals and options take effect."""
    await hass.config_entries.async_reload(entry.entry_id)
