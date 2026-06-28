"""Binary sensor entities for gateway outputs on the Renson Arean integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory

from .const import DOMAIN, KNOWN_OUTPUTS, UNKNOWN_OUTPUTS
from .entity import RensonAreanEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import RensonCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Renson Arean binary sensor entities."""
    coordinator: RensonCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = []
    for output_id, meta in KNOWN_OUTPUTS.items():
        entities.append(RensonAreanOutputSensor(coordinator, output_id, meta["name"], meta["device_class"]))
    for output_id in UNKNOWN_OUTPUTS:
        entities.append(RensonAreanDiagnosticOutputSensor(coordinator, output_id))
    entities.append(RensonBackupHeaterSensor(coordinator))
    entities.append(RensonSilentModeRecurrentSensor(coordinator))

    async_add_entities(entities)


class RensonAreanOutputSensor(RensonAreanEntity, BinarySensorEntity):
    """Binary sensor for a known HVAC gateway output."""

    def __init__(
        self,
        coordinator: RensonCoordinator,
        output_id: int,
        name: str,
        device_class_str: str,
    ) -> None:
        super().__init__(coordinator)
        self._output_id = output_id
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.device_id}_output_{output_id}"
        self._attr_device_class = _str_to_device_class(device_class_str)

    @property
    def is_on(self) -> bool | None:
        output = self.coordinator.data.outputs.get(self._output_id)
        if output is None:
            return None
        return output.status == 1


class RensonAreanDiagnosticOutputSensor(RensonAreanEntity, BinarySensorEntity):
    """Diagnostic binary sensor for a gateway output with unknown function."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    # Disabled by default — enable once the output's function is confirmed
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: RensonCoordinator, output_id: int) -> None:
        super().__init__(coordinator)
        self._output_id = output_id
        self._attr_name = f"Gateway output {output_id}"
        self._attr_unique_id = f"{coordinator.device_id}_output_{output_id}"

    @property
    def is_on(self) -> bool | None:
        output = self.coordinator.data.outputs.get(self._output_id)
        if output is None:
            return None
        return output.status == 1


class RensonBackupHeaterSensor(RensonAreanEntity, BinarySensorEntity):
    """Read-only state of the backup heater as configured in the OpenMotics plugin."""

    _attr_name = "Backup heater"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: RensonCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_backup_heater"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.plugin_config.backup_heater


class RensonSilentModeRecurrentSensor(RensonAreanEntity, BinarySensorEntity):
    """Read-only state of the recurring silent mode schedule in the OpenMotics plugin."""

    _attr_name = "Silent mode recurring"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: RensonCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_silent_mode_recurrent"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.plugin_config.silent_mode_recurrent


_DEVICE_CLASS_MAP: dict[str, BinarySensorDeviceClass] = {
    "opening": BinarySensorDeviceClass.OPENING,
    "running": BinarySensorDeviceClass.RUNNING,
}


def _str_to_device_class(value: str) -> BinarySensorDeviceClass | None:
    return _DEVICE_CLASS_MAP.get(value)
