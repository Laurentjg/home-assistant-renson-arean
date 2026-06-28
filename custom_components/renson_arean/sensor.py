"""Sensor entities for the Renson Arean integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfTime

from .const import BYPASS_OUTPUT_ID, DOMAIN
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
    """Set up Renson Arean sensor entities."""
    coordinator: RensonCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            RensonSteeringPowerSensor(coordinator),
            RensonBypassValveSensor(coordinator),
            RensonSilentMaxTimeSensor(coordinator),
            RensonSilentStartHourSensor(coordinator),
            RensonSilentRunningTimeSensor(coordinator),
            RensonEnergySourceSensor(coordinator),
            RensonHeatPumpStateSensor(coordinator),
            RensonCommissioningStateSensor(coordinator),
        ]
    )


class RensonSteeringPowerSensor(RensonAreanEntity, SensorEntity):
    """Steering power (0–100%) — how hard rensonheatpumplogic is driving the pump."""

    _attr_name = "Steering power"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: RensonCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_steering_power"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.thermostat_status.steering_power


class RensonBypassValveSensor(RensonAreanEntity, SensorEntity):
    """Bypass valve — mixing valve that controls the supply temperature (gateway dimmer value)."""

    _attr_name = "Bypass valve"
    # No % unit: the gateway reports a raw dimmer value (scale undetermined)
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: RensonCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_bypass_valve"

    @property
    def native_value(self) -> int | None:
        output = self.coordinator.data.outputs.get(BYPASS_OUTPUT_ID)
        if output is None:
            return None
        return output.dimmer


class RensonSilentMaxTimeSensor(RensonAreanEntity, SensorEntity):
    """Maximum duration of a single silent mode activation (hours)."""

    _attr_name = "Silent mode max duration"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: RensonCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_silent_max_time"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.plugin_config.silent_max_time


class RensonSilentStartHourSensor(RensonAreanEntity, SensorEntity):
    """Time of day at which recurring silent mode activates (e.g. '22:00')."""

    _attr_name = "Silent mode start time"

    def __init__(self, coordinator: RensonCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_silent_start_hour"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.plugin_config.silent_mode_start_hour


class RensonSilentRunningTimeSensor(RensonAreanEntity, SensorEntity):
    """How long silent mode has been running in the current activation (hours)."""

    _attr_name = "Silent mode running time"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: RensonCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_silent_running_time"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.plugin_config.silent_current_running_time


class RensonEnergySourceSensor(RensonAreanEntity, SensorEntity):
    """Heat pump energy source type as configured in the OpenMotics plugin."""

    _attr_name = "Energy source"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: RensonCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_energy_source"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.plugin_config.type_energy_source


class RensonHeatPumpStateSensor(RensonAreanEntity, SensorEntity):
    """Operational state of the rensonheatpumplogic plugin (e.g. 'Logic')."""

    _attr_name = "Heat pump logic state"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: RensonCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_hp_state"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.plugin_config.state


class RensonCommissioningStateSensor(RensonAreanEntity, SensorEntity):
    """Commissioning state reported by the rensonheatpumplogic plugin."""

    _attr_name = "Commissioning state"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: RensonCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_commissioning_state"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.plugin_config.commissioning_state
