"""HTTP client for the OpenMotics gateway.

Free of Home Assistant imports: the caller supplies the aiohttp session, so the
session can be Home Assistant's own (and a test's can be a fake one).

Two security properties live here and nowhere else:
* the token exists only in memory and is never written to disk (M-01);
* credentials are stripped from every log line, because the gateway takes them
  as query parameters and naive URL logging would leak them (M-03, SEC-13).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from . import endpoints

_LOGGER = logging.getLogger(__name__)

# The token has a one-hour TTL; refresh a little early (CN-04).
TOKEN_TTL = timedelta(hours=1)
TOKEN_REFRESH_MARGIN = timedelta(minutes=5)

REDACTED_PARAMS = frozenset({"username", "password", "token"})


class RensonError(Exception):
    """Base class for every error this client raises."""


class RensonAuthError(RensonError):
    """The gateway rejected the credentials or the token."""


class RensonConnectionError(RensonError):
    """The gateway could not be reached."""


class RensonApiError(RensonError):
    """The gateway answered, but reported the call as failed."""


def redact(params: dict[str, Any]) -> dict[str, Any]:
    """Return `params` with every credential replaced by a placeholder."""
    return {
        key: "***" if key in REDACTED_PARAMS else value for key, value in params.items()
    }


class RensonClient:
    """Talk to the local gateway on the Brain module."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
    ) -> None:
        """Store the connection details; no I/O happens here."""
        self._session = session
        self._host = host
        self._username = username
        self._password = password
        self._token: str | None = None
        self._token_expiry: datetime | None = None

    @property
    def host(self) -> str:
        """The gateway host this client talks to."""
        return self._host

    async def login(self) -> None:
        """Obtain a token. Raises RensonAuthError on bad credentials."""
        params = {"username": self._username, "password": self._password}
        data = await self._request(endpoints.LOGIN, params, authenticated=False)
        token = data.get("token")
        if not token:
            raise RensonAuthError("Gateway returned no token")
        self._token = token
        self._token_expiry = datetime.now() + TOKEN_TTL

    async def _ensure_token(self) -> None:
        if self._token is None or self._token_expiry is None:
            await self.login()
        elif datetime.now() >= self._token_expiry - TOKEN_REFRESH_MARGIN:
            await self.login()

    async def _request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        """Perform one GET and return the decoded body."""
        call_params = dict(params or {})
        if authenticated:
            await self._ensure_token()
            call_params["token"] = self._token

        _LOGGER.debug("GET %s %s", path, redact(call_params))
        try:
            async with self._session.get(
                f"https://{self._host}/{path}", params=call_params
            ) as response:
                if response.status == 401:
                    self._token = None
                    raise RensonAuthError(f"Gateway rejected the request to {path}")
                response.raise_for_status()
                data = await response.json(content_type=None)
        except aiohttp.ClientResponseError as err:
            raise RensonApiError(f"{path} returned HTTP {err.status}") from err
        except aiohttp.ClientError as err:
            raise RensonConnectionError(f"{path} failed: {err}") from err

        if not isinstance(data, dict):
            raise RensonApiError(f"{path} returned an unexpected body")
        if data.get("success") is False:
            raise RensonApiError(f"{path} failed: {data.get('msg')}")
        return data

    # --- reads ---------------------------------------------------------------

    async def get_version(self) -> dict[str, Any]:
        """Read get_version."""
        return await self._request(endpoints.GET_VERSION)

    async def get_status(self) -> dict[str, Any]:
        """Read get_status."""
        return await self._request(endpoints.GET_STATUS)

    async def get_system_status(self) -> dict[str, Any]:
        """Read get_system_status."""
        return await self._request(endpoints.GET_SYSTEM_STATUS)

    async def get_modules_information(self) -> dict[str, Any]:
        """Read get_modules_information."""
        return await self._request(endpoints.GET_MODULES_INFORMATION)

    async def get_plugins(self) -> dict[str, Any]:
        """Read get_plugins."""
        return await self._request(endpoints.GET_PLUGINS)

    async def get_output_status(self) -> dict[str, Any]:
        """Read get_output_status."""
        return await self._request(endpoints.GET_OUTPUT_STATUS)

    async def get_input_status(self) -> dict[str, Any]:
        """Read get_input_status."""
        return await self._request(endpoints.GET_INPUT_STATUS)

    async def get_plugin_logs(self) -> dict[str, Any]:
        """Read get_plugin_logs — a rolling buffer of 100 lines per app (CN-11)."""
        return await self._request(endpoints.GET_PLUGIN_LOGS)

    async def get_thermostat_group_status(self) -> dict[str, Any]:
        """Read get_thermostat_group_status."""
        return await self._request(endpoints.GET_THERMOSTAT_GROUP_STATUS)

    async def get_plugin_config(self, app: str) -> dict[str, Any]:
        """Read the configuration of one app."""
        return await self._request(endpoints.plugin_config(app))

    # --- writes --------------------------------------------------------------
    #
    # These are the only write paths in the integration. There is deliberately
    # no generic "write any Modbus register" primitive (SEC-10), and the two
    # heat pump apps are never written to at all (§5.6, §5.7).

    async def write_thermostat_register(
        self, slave: int, register: int, value: int
    ) -> None:
        """Write one register of the wall thermostat over Modbus (§5.4)."""
        await self._request(
            endpoints.WRITE_MODBUS_REGISTER,
            {"slaveaddress": slave, "registeraddress": register, "value": value},
        )

    async def set_current_setpoint(self, thermostat_id: int, temperature: float) -> None:
        """Write the setpoint over the generic OpenMotics API (§5.4 fallback)."""
        await self._request(
            endpoints.SET_CURRENT_SETPOINT,
            {"thermostat": thermostat_id, "temperature": temperature},
        )

    async def set_thermostat_group_mode(self, group_id: int, mode: str) -> None:
        """Set the heating/cooling mode of a thermostat group (§5.4)."""
        await self._request(
            endpoints.SET_THERMOSTAT_GROUP,
            {"thermostat_group_id": group_id, "mode": mode},
        )
