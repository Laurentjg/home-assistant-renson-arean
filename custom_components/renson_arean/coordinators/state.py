"""Fast-changing state at 30 s (§6.2).

Two very different things share this coordinator, and on purpose. The outputs
come from the gateway; the log comes from `rensonheatpumplogic`. The log is
here rather than with the five-minute config coordinator because the buffer
holds only a hundred lines — about a minute and a half — so a slower poll would
simply lose cycles (CN-11).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from ..api import models
from ..applog import reader, ssr
from ..const import APP_LOGIC, SOURCE_GATEWAY_CORE, source_app_log
from ..health import STATUS_ERROR, STATUS_OK
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

        app_health = {app: ssr.parse_app_health(lines) for app, lines in logs.items()}
        return StateData(
            outputs=outputs,
            brain_inputs=brain_inputs,
            ssr=snapshot,
            app_health=app_health,
        )
