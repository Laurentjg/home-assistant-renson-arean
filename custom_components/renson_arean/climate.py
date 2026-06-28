"""Climate entity for the Renson Arean heat pump."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import HVACAction, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .const import (
    DOMAIN,
    OM_PRESET_TO_HA,
    PRESET_AWAY,
    PRESET_MANUAL,
    PRESET_SCHEDULE,
    PRESET_MAP,
)
from .entity import RensonAreanEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import RensonCoordinator

_LOGGER = logging.getLogger(__name__)

OM_MODE_TO_HVAC: dict[str, HVACMode] = {
    "heating": HVACMode.HEAT,
    "cooling": HVACMode.COOL,
    "HEATING": HVACMode.HEAT,
    "COOLING": HVACMode.COOL,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renson Arean climate entity."""
    coordinator: RensonCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RensonAreanClimate(coordinator)])


class RensonAreanClimate(RensonAreanEntity, ClimateEntity):
    """Central climate control entity for the Renson Arean heat pump."""

    _attr_name = "Heat pump"
    _attr_unique_id: str
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL]
    _attr_preset_modes = [PRESET_SCHEDULE, PRESET_AWAY, PRESET_MANUAL]
    _attr_min_temp = 10.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: RensonCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_climate"

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.data.thermostat_status.actual_temperature

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.data.thermostat_status.setpoint

    @property
    def hvac_mode(self) -> HVACMode | None:
        mode = self.coordinator.data.thermostat_status.mode
        return OM_MODE_TO_HVAC.get(mode or "") if mode else None

    @property
    def hvac_action(self) -> HVACAction | None:
        """Derive running state from steering_power (0 = idle)."""
        steering = self.coordinator.data.thermostat_status.steering_power
        if steering is None:
            return None
        if steering > 0:
            mode = self.coordinator.data.thermostat_status.mode or ""
            return HVACAction.COOLING if "cool" in mode.lower() else HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        preset = self.coordinator.data.thermostat_status.active_preset
        return OM_PRESET_TO_HA.get(preset or "") if preset else None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature via Modbus slave 41 register 20."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.coordinator.api.set_setpoint(temperature)
        # ~5 sec latency: RensonThermostat plugin polls slave 41 every 5 seconds;
        # optimistic state update so HA responds immediately
        self.coordinator.data.thermostat_status.setpoint = temperature
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set heating or cooling mode via set_thermostat_group."""
        om_mode = "heating" if hvac_mode == HVACMode.HEAT else "cooling"
        await self.coordinator.api.set_hvac_mode(om_mode)
        self.coordinator.data.thermostat_status.mode = om_mode
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset via Modbus slave 41 register 3."""
        preset_value = PRESET_MAP.get(preset_mode)
        if preset_value is None:
            _LOGGER.warning("Unknown preset mode: %s", preset_mode)
            return
        await self.coordinator.api.set_preset(preset_value)
        # Reverse-map to OM preset name for optimistic update
        ha_to_om = {PRESET_SCHEDULE: "auto", PRESET_AWAY: "away", PRESET_MANUAL: "manual"}
        self.coordinator.data.thermostat_status.active_preset = ha_to_om.get(preset_mode)
        self.async_write_ha_state()
