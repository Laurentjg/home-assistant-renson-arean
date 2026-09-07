"""Thermostat status at 10 s (§6.2).

This is the one thing the user watches live, and the one thing they change. It
reads over the generic OpenMotics layer (L2) and never over the app config
(L3): the two disagree, and L3 is not the active source when
`use_config_thermostats` is off (§5.4).
"""

from __future__ import annotations

from ..api import models
from ..const import SOURCE_GATEWAY_CORE
from ..health import STATUS_OK
from . import RensonCoordinator


class ThermostatCoordinator(RensonCoordinator[dict[int, models.ThermostatState]]):
    """Read the thermostat groups."""

    async def _fetch(self) -> dict[int, models.ThermostatState]:
        thermostats = models.parse_thermostat_status(
            await self.client.get_thermostat_group_status()
        )
        self.health.report(
            SOURCE_GATEWAY_CORE, STATUS_OK, f"{len(thermostats)} thermostaat/-aten"
        )
        return thermostats
