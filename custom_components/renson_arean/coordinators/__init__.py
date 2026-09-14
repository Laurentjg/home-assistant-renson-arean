"""The four coordinators of §6.2 and the runtime object that holds them.

There is deliberately no single poll interval. Each source gets the interval
that matches how fast it actually changes, so the thermostat can be current
without the topology being re-read every ten seconds.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, TypeVar

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from ..api.client import RensonAuthError, RensonError
from ..const import DOMAIN

if TYPE_CHECKING:
    from datetime import timedelta

    from homeassistant.core import HomeAssistant

    from ..api.client import RensonClient
    from ..health import SourceHealthTracker

_LOGGER = logging.getLogger(__package__)

_T = TypeVar("_T")


class RensonCoordinator(DataUpdateCoordinator[_T]):
    """Shared plumbing: one client, one health tracker, one interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: RensonClient,
        health: SourceHealthTracker,
        name: str,
        interval: timedelta,
    ) -> None:
        """Set up the coordinator without doing any I/O."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}.{name}",
            update_interval=interval,
        )
        self.client = client
        self.health = health

    async def _async_update_data(self) -> _T:
        """Fetch one cycle, mapping client errors onto Home Assistant's."""
        try:
            return await self._fetch()
        except RensonAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except RensonError as err:
            raise UpdateFailed(str(err)) from err

    async def _fetch(self) -> _T:
        """Do the actual work. Implemented by each coordinator."""
        raise NotImplementedError
