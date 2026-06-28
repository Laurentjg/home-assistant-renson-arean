"""DataUpdateCoordinator for the Renson Arean integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RensonAuthError, RensonConnectionError, RensonData, ThermostatStatus
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .api import RensonApiClient

_LOGGER = logging.getLogger(__name__)


class RensonCoordinator(DataUpdateCoordinator[RensonData]):
    """Fetch all Renson Arean data in one coordinator poll cycle."""

    def __init__(self, hass: HomeAssistant, api: RensonApiClient, device_id: str) -> None:
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.api = api
        self.device_id = device_id

    async def _async_update_data(self) -> RensonData:
        """Fetch data from all relevant gateway endpoints."""
        try:
            thermostat_status = await self.api.get_thermostat_status()
            outputs = await self.api.get_output_status()
            plugin_config = await self.api.get_plugin_config()
        except RensonAuthError as err:
            raise ConfigEntryAuthFailed from err
        except RensonConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err

        return RensonData(
            thermostat_status=thermostat_status,
            outputs=outputs,
            plugin_config=plugin_config,
            gateway_serial=self.device_id,
        )
