"""The reload-topology button (D-04)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .entity import GatewayEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import RensonConfigEntry


class ReloadTopologyButton(GatewayEntity, ButtonEntity):
    """Re-read the modules and apps without waiting for the 15-minute cycle."""

    _entity_domain = "button"

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Refresh the topology now."""
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RensonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button."""
    runtime = entry.runtime_data
    async_add_entities(
        [
            ReloadTopologyButton(
                runtime.topology,
                runtime.devices.brain,
                runtime.devices.brain_origin,
                "reload_topology",
                "Herlaad topologie",
                "get_modules_information",
            )
        ]
    )
