"""The Renson Arean integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import RensonApiClient, RensonAuthError, RensonConnectionError
from .const import (
    CONF_HOST,
    CONF_MODBUS_SLAVE,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_MODBUS_SLAVE,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import RensonCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Renson Arean from a config entry."""
    modbus_slave: int = entry.options.get(CONF_MODBUS_SLAVE, DEFAULT_MODBUS_SLAVE)

    api = RensonApiClient(
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        modbus_slave=modbus_slave,
    )

    try:
        serial = await api.get_gateway_serial()
    except RensonAuthError as err:
        await api.close()
        raise ConfigEntryAuthFailed from err
    except RensonConnectionError as err:
        await api.close()
        raise ConfigEntryNotReady from err

    coordinator = RensonCoordinator(hass, api, device_id=serial)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the Renson Arean config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: RensonCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.close()
    return unload_ok


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change so the new slave address takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)
