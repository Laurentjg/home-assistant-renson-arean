"""The thermostat.

The climate entity lives on the thermostat device, not on the app device
(D-10): the app is a driver, the thermostat is the thing the user thinks about.
Reading always goes over the OpenMotics layer, which disagrees with the app's
own configuration section and is the one that is actually in charge (§5.4).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later

from .const import (
    OM_PRESET_TO_HA,
    PRESET_AWAY,
    PRESET_MANUAL,
    PRESET_SCHEDULE,
    SETPOINT_MAX,
    SETPOINT_MIN,
    SOURCE_GATEWAY_CORE,
)
from .entity import RensonEntity
from .thermostat.backends import select_backend
from .thermostat.confirm import REFRESH_SCHEDULE, ConfirmationWindow

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import RensonConfigEntry, RensonRuntime

_LOGGER = logging.getLogger(__name__)

OM_MODE_TO_HVAC = {"heating": HVACMode.HEAT, "cooling": HVACMode.COOL}
HVAC_TO_OM_MODE = {value: key for key, value in OM_MODE_TO_HVAC.items()}


class RensonThermostat(RensonEntity, ClimateEntity):
    """One thermostat zone: the wall unit's reading, steered via the OM controller."""

    _attr_translation_key = "renson_thermostat"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL]
    _attr_preset_modes = [PRESET_SCHEDULE, PRESET_AWAY, PRESET_MANUAL]
    _attr_min_temp = SETPOINT_MIN
    _attr_max_temp = SETPOINT_MAX
    _attr_target_temperature_step = 0.5
    _attr_name = None
    _entity_domain = "climate"

    def __init__(
        self,
        runtime: RensonRuntime,
        om_id: int,
        device,
        origin,
    ) -> None:
        """Bind the entity to one OpenMotics thermostat."""
        super().__init__(
            runtime.thermostat,
            device,
            origin,
            "climate",
            None,
            SOURCE_GATEWAY_CORE,
            "get_thermostat_group_status",
        )
        self._runtime = runtime
        self._om_id = om_id
        self._window = runtime.windows.setdefault(om_id, ConfirmationWindow())

    @property
    def _state(self):
        data = self.coordinator.data
        return data.get(self._om_id) if data else None

    @property
    def available(self) -> bool:
        """Available while the gateway reports this thermostat."""
        return super().available and self._state is not None

    @property
    def current_temperature(self) -> float | None:
        """The measured room temperature."""
        return self._state.actual_temperature if self._state else None

    @property
    def target_temperature(self) -> float | None:
        """The setpoint, with a just-written value winning until confirmed."""
        reported = self._state.setpoint if self._state else None
        return self._window.resolve("setpoint", reported)

    @property
    def preset_mode(self) -> str | None:
        """The active preset, with a just-written value winning until confirmed."""
        reported = (
            OM_PRESET_TO_HA.get(self._state.preset or "") if self._state else None
        )
        return self._window.resolve("preset", reported)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Heating or cooling — a property of the group, not of one thermostat."""
        if not self._state:
            return None
        return OM_MODE_TO_HVAC.get(self._state.group_mode or "")

    @property
    def hvac_action(self) -> HVACAction | None:
        """Whether the controller asks for heat (or cold) right now (§5.4).

        Fed by the OM controller: demand while hysteresis is active or steering
        power is above zero. It says the controller asks, not that the heat pump
        delivers — on 2026-09-12 it kept asking with the monobloc switched off.
        """
        state = self._state
        if state is None:
            return None
        if not (state.hysteresis_active or (state.steering_power or 0) > 0):
            return HVACAction.IDLE
        if state.group_mode == "cooling":
            return HVACAction.COOLING
        return HVACAction.HEATING

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The fields 2026.6.0 left unread (§5.4)."""
        attributes = super().extra_state_attributes
        # It steers the zone through the OM controller, not the wall unit.
        attributes["layer"] = "L2"
        state = self._state
        if state is None:
            return attributes
        attributes.update(
            {
                "output0": state.output0,
                "output1": state.output1,
                "control_mode": state.control_mode,
                "thermostat_group": state.group_id,
                "overrule_setpoint": state.overrule_setpoint,
                "overrule_reason": state.overrule_reason,
                # Tells a deviating setpoint imposed by the installation apart
                # from one the user set — what the confirmation window needs to
                # know whether a write failed or was overruled.
                "overrule_source": state.overrule_source,
                "write_backend": self._backend().name,
            }
        )
        return attributes

    def _backend(self):
        config = self._runtime.config.data
        return select_backend(
            self._runtime.client,
            self._om_id,
            config.thermostat_app if config else None,
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Write a new setpoint and confirm it quickly (P-09)."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._write("setpoint", temperature, self._backend().set_setpoint)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Write a new preset."""
        await self._write("preset", preset_mode, self._backend().set_preset)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the mode of the whole thermostat group.

        Several thermostats in one group share this setting; that is stated
        rather than hidden (§5.4).
        """
        state = self._state
        mode = HVAC_TO_OM_MODE.get(hvac_mode)
        if state is None or mode is None:
            return
        await self._runtime.client.set_thermostat_group_mode(state.group_id, mode)
        await self._confirm()

    async def _write(self, key: str, value: Any, write) -> None:
        try:
            await write(value)
        except ValueError as err:
            # A wrong or malicious script must not put nonsense on the bus
            # (SEC-12).
            raise HomeAssistantError(str(err)) from err

        # The UI reacts within a frame, before any poll comes back.
        self._window.start(key, value)
        self.async_write_ha_state()
        await self._confirm()

    async def _confirm(self) -> None:
        """Ask the gateway again on the schedule of §6.2.

        The physical chain is slow: the app polls the thermostat every 5 s, so
        a confirmation cannot arrive sooner however fast we poll.
        """
        for delay in REFRESH_SCHEDULE:
            async_call_later(self.hass, delay, self._scheduled_refresh)

    async def _scheduled_refresh(self, _now) -> None:
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RensonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one climate entity per active OpenMotics thermostat."""
    runtime = entry.runtime_data
    async_add_entities(
        RensonThermostat(runtime, om_id, device, origin)
        for om_id, (device, origin) in runtime.devices.thermostats.items()
    )
