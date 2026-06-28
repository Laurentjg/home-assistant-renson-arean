"""Switch entities for the Renson Arean integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .entity import RensonAreanEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import RensonCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Renson Arean switch entities."""
    coordinator: RensonCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RensonSilentModeSwitch(coordinator)])


class RensonSilentModeSwitch(RensonAreanEntity, SwitchEntity):
    """Silent mode — reduces noise from the outdoor unit (compressor / fan)."""

    _attr_name = "Silent mode"

    def __init__(self, coordinator: RensonCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_silent_mode"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.plugin_config.silent_mode

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.set_silent_mode(True)
        self.coordinator.data.plugin_config.silent_mode = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.set_silent_mode(False)
        self.coordinator.data.plugin_config.silent_mode = False
        self.async_write_ha_state()
