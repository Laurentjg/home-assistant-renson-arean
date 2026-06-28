"""Base entity for the Renson Arean integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import RensonCoordinator


class RensonAreanEntity(CoordinatorEntity["RensonCoordinator"]):
    """Base entity — all Renson Arean entities share this device_info."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RensonCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name="Renson Arean",
            manufacturer="Renson",
            model="Arean 5kW",
            sw_version="OpenMotics v3.13.4",
        )
