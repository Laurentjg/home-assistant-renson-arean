"""Fast-changing state at 30 s (§6.2).

Two very different things share this coordinator, and on purpose. The outputs
come from the gateway; the log comes from `rensonheatpumplogic`. The log is
here rather than with the five-minute config coordinator because the buffer
holds only a hundred lines — about a minute and a half — so a slower poll would
simply lose cycles (CN-11).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Callable

from homeassistant.util import dt as dt_util

from ..api import models
from ..applog import reader, ssr
from ..const import (
    APP_LOGIC,
    HEATPUMP_ARRAYS,
    HEATPUMP_FRESHNESS,
    SOURCE_GATEWAY_CORE,
    SOURCE_HARDWARE_HEATPUMP,
    source_app_log,
)
from ..health import STATUS_ERROR, STATUS_MISSING, STATUS_OK, freshness
from . import RensonCoordinator

if TYPE_CHECKING:
    from datetime import timedelta

    from homeassistant.core import HomeAssistant

    from ..api.client import RensonClient
    from ..health import SourceHealthTracker


@dataclass(frozen=True)
class StateData:
    """One cycle of fast-changing state."""

    outputs: dict[int, models.OutputState] = field(default_factory=dict)
    brain_inputs: dict[int, bool] = field(default_factory=dict)
    ssr: ssr.SsrSnapshot = field(default_factory=ssr.SsrSnapshot)
    app_health: dict[str, ssr.AppHealth] = field(default_factory=dict)
    # `hardware:heatpump` (D-17): None while the log cannot tell, which is
    # different from the monobloc being gone.
    heatpump_reachable: bool | None = None
    heatpump_seen: datetime | None = None


class StateCoordinator(RensonCoordinator[StateData]):
    """Read the outputs, the Brain inputs and the app logs."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: RensonClient,
        health: SourceHealthTracker,
        interval: timedelta,
        app_version: Callable[[str], str | None],
    ) -> None:
        """`app_version` comes from the topology coordinator (D-14 d)."""
        super().__init__(hass, client, health, "state", interval)
        self._app_version = app_version
        self._started: datetime | None = None
        # Remembered across polls: the buffer holds about a minute and a half,
        # shorter than the freshness limit.
        self._heatpump_seen: datetime | None = None

    async def _fetch(self) -> StateData:
        outputs = models.parse_output_status(await self.client.get_output_status())
        brain_inputs = models.parse_input_status(await self.client.get_input_status())
        self.health.report(
            SOURCE_GATEWAY_CORE, STATUS_OK, f"{len(outputs)} uitgangen"
        )

        logs = reader.parse_logs(await self.client.get_plugin_logs())
        snapshot = ssr.parse_ssr(logs.get(APP_LOGIC, []), self._app_version(APP_LOGIC))

        if snapshot.rejected:
            self.health.report(
                source_app_log(APP_LOGIC), STATUS_ERROR, "; ".join(snapshot.rejected)
            )
        elif snapshot.arrays:
            self.health.report(
                source_app_log(APP_LOGIC),
                STATUS_OK,
                f"{len(snapshot.arrays)} SSR-arrays",
            )
        else:
            # The SSR lines are only written on change, so an empty buffer is
            # normal after a restart and is not a fault (§6.2, L-02).
            self.health.report(
                source_app_log(APP_LOGIC),
                STATUS_OK,
                "nog geen SSR-regels in de logbuffer",
            )

        heatpump_reachable = self._heatpump_reachable(snapshot)

        app_health = {app: ssr.parse_app_health(lines) for app, lines in logs.items()}
        return StateData(
            outputs=outputs,
            brain_inputs=brain_inputs,
            ssr=snapshot,
            app_health=app_health,
            heatpump_reachable=heatpump_reachable,
            heatpump_seen=self._heatpump_seen,
        )

    def _heatpump_reachable(self, snapshot: ssr.SsrSnapshot) -> bool | None:
        """Judge `hardware:heatpump` by the age of the monobloc arrays (§5.0).

        The log timestamps are the gateway's local time, so they are compared
        against local time without a zone.
        """
        now = dt_util.now().replace(tzinfo=None)
        if self._started is None:
            self._started = now
        for key in HEATPUMP_ARRAYS:
            seen = snapshot.seen.get(key)
            if seen is not None and (
                self._heatpump_seen is None or seen > self._heatpump_seen
            ):
                self._heatpump_seen = seen

        if snapshot.rejected:
            # The log cannot be read, so nothing can be said about the device
            # behind it: "we cannot read it" is not "it is gone" (§5.8).
            return None

        reachable = freshness(
            self._heatpump_seen, self._started, now, HEATPUMP_FRESHNESS
        )
        if reachable is True:
            self.health.report(SOURCE_HARDWARE_HEATPUMP, STATUS_OK)
        elif reachable is False:
            self.health.report(
                SOURCE_HARDWARE_HEATPUMP,
                STATUS_MISSING,
                f"geen {' of '.join(HEATPUMP_ARRAYS)} in "
                f"{int(HEATPUMP_FRESHNESS.total_seconds() // 60)} minuten",
            )
        return reachable
