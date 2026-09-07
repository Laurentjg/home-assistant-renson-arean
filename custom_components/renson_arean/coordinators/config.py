"""App configuration at 5 minutes (§6.2).

These are settings, not measurements. 2026.9.0 only reads them: two of the
three apps are read-only by design (D-06, SEC-11), and the third is written to
only along the proven setpoint and preset paths of §5.4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from ..api import models
from ..api.client import RensonApiError
from ..const import APP_HEATPUMP, APP_LOGIC, APP_THERMOSTAT, source_app_config
from ..health import STATUS_ERROR, STATUS_OK
from . import RensonCoordinator

if TYPE_CHECKING:
    from datetime import timedelta

    from homeassistant.core import HomeAssistant

    from ..api.client import RensonClient
    from ..health import SourceHealthTracker


@dataclass(frozen=True)
class ConfigData:
    """The parsed configuration of every app that answered."""

    logic: models.LogicConfig | None = None
    thermostat_app: models.ThermostatAppConfig | None = None
    heatpump_app: models.HeatPumpAppConfig | None = None
    raw: dict[str, dict[str, Any]] = field(default_factory=dict)


class ConfigCoordinator(RensonCoordinator[ConfigData]):
    """Read the configuration of the apps the gateway reports."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: RensonClient,
        health: SourceHealthTracker,
        interval: timedelta,
        apps: Callable[[], list[str]],
    ) -> None:
        """`apps` comes from the topology coordinator, so nothing is hardcoded (P-05)."""
        super().__init__(hass, client, health, "config", interval)
        self._apps = apps

    async def _fetch(self) -> ConfigData:
        raw: dict[str, dict[str, Any]] = {}
        for app in self._apps():
            try:
                raw[app] = await self.client.get_plugin_config(app)
            except RensonApiError as err:
                # One app refusing its config must not take the others down (P-06).
                self.health.report(source_app_config(app), STATUS_ERROR, str(err))
                continue
            self.health.report(source_app_config(app), STATUS_OK)

        return ConfigData(
            logic=(
                models.parse_logic_config(raw[APP_LOGIC]) if APP_LOGIC in raw else None
            ),
            thermostat_app=(
                models.parse_thermostat_app_config(raw[APP_THERMOSTAT])
                if APP_THERMOSTAT in raw
                else None
            ),
            heatpump_app=(
                models.parse_heatpump_app_config(raw[APP_HEATPUMP])
                if APP_HEATPUMP in raw
                else None
            ),
            raw=raw,
        )
