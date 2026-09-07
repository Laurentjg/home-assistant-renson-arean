"""Which modules and apps exist, and at which version (§6.2, §10).

Changes rarely, so it polls slowly. A changed app version is worth one INFO
line — it is the trigger for everything that hangs on the app's internals
(D-14).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..api import models
from ..const import SOURCE_GATEWAY_CORE, source_app_runtime
from ..health import STATUS_OK
from . import RensonCoordinator

if TYPE_CHECKING:
    from datetime import timedelta

    from homeassistant.core import HomeAssistant

    from ..api.client import RensonClient
    from ..health import SourceHealthTracker

_LOGGER = logging.getLogger(__package__)


class TopologyCoordinator(RensonCoordinator[models.Topology]):
    """Read the modules, the apps and the firmware versions."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: RensonClient,
        health: SourceHealthTracker,
        interval: timedelta,
    ) -> None:
        """Set up the coordinator."""
        super().__init__(hass, client, health, "topology", interval)
        self._versions: dict[str, str | None] = {}

    async def _fetch(self) -> models.Topology:
        version = models.parse_version(await self.client.get_version())
        updates = models.parse_system_status(await self.client.get_system_status())
        modules = models.parse_modules(await self.client.get_modules_information())
        apps = models.parse_plugins(await self.client.get_plugins())

        self.health.report(SOURCE_GATEWAY_CORE, STATUS_OK)
        for app in apps.values():
            self.health.report(
                source_app_runtime(app.name),
                STATUS_OK,
                f"versie {app.version}, status {app.status}",
            )
            self._note_version_change(app)

        return models.Topology(
            version=version, updates=updates, modules=modules, apps=apps
        )

    def _note_version_change(self, app: models.AppInfo) -> None:
        previous = self._versions.get(app.name, ...)
        if previous is not ... and previous != app.version:
            _LOGGER.info(
                "app %s ging van versie %s naar %s", app.name, previous, app.version
            )
        self._versions[app.name] = app.version

    def app_version(self, app: str) -> str | None:
        """The version of one app, or None while it is unknown."""
        if not self.data:
            return None
        info = self.data.apps.get(app)
        return info.version if info else None
