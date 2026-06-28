"""Renson Arean API client — OpenMotics gateway local REST API."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class RensonAuthError(Exception):
    """Raised when authentication fails (401 or bad credentials)."""


class RensonConnectionError(Exception):
    """Raised when the gateway cannot be reached."""


@dataclass
class ThermostatStatus:
    """Parsed status from get_thermostat_group_status."""

    actual_temperature: float | None
    setpoint: float | None
    active_preset: str | None
    mode: str | None
    steering_power: int | None


@dataclass
class OutputStatus:
    """Status of a single gateway output."""

    output_id: int
    status: int  # 0 = off, 1 = on
    dimmer: int | None  # 0–100 for dimmer outputs, None for relays


@dataclass
class PluginConfig:
    """Parsed data from plugins/rensonheatpumplogic/get_config."""

    # silent_mode_config
    silent_mode: bool = False
    silent_mode_recurrent: bool = False
    silent_mode_start_hour: str | None = None
    silent_max_time: float | None = None
    silent_current_running_time: float | None = None
    # heatpump_config
    backup_heater: bool = False
    type_energy_source: str | None = None
    # state_config
    state: str | None = None
    commissioning_state: str | None = None


@dataclass
class RensonData:
    """All coordinator data in one place."""

    thermostat_status: ThermostatStatus
    outputs: dict[int, OutputStatus] = field(default_factory=dict)
    plugin_config: PluginConfig = field(default_factory=PluginConfig)
    gateway_serial: str = ""


class RensonApiClient:
    """Async API client for the OpenMotics local gateway."""

    def __init__(self, host: str, username: str, password: str, modbus_slave: int = 41) -> None:
        self._base_url = f"https://{host}"
        self._username = username
        self._password = password
        self._modbus_slave = modbus_slave
        self._token: str | None = None
        self._token_expiry: datetime | None = None
        self._session: aiohttp.ClientSession | None = None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # ssl=False: gateway uses a self-signed certificate (CN-05)
            connector = aiohttp.TCPConnector(ssl=False)  # noqa: S501
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def close(self) -> None:
        """Close the underlying aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _ensure_token(self) -> None:
        if (
            self._token_expiry is None
            or datetime.now() >= self._token_expiry - timedelta(minutes=5)
        ):
            await self._login()

    async def _login(self) -> None:
        """Authenticate against the gateway; token TTL is 1 hour (CN-04)."""
        session = self._get_session()
        try:
            async with session.get(
                f"{self._base_url}/login",
                params={"username": self._username, "password": self._password},
            ) as resp:
                if resp.status == 401:
                    raise RensonAuthError("Invalid credentials")
                resp.raise_for_status()
                data = await resp.json()
                if not data.get("success"):
                    raise RensonAuthError(f"Login failed: {data}")
                self._token = data["token"]
                self._token_expiry = datetime.now() + timedelta(hours=1)
        except aiohttp.ClientError as err:
            raise RensonConnectionError(f"Cannot connect to gateway: {err}") from err

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Perform an authenticated GET request.

        Auth method: token as query parameter (no Authorization header — architecture.md §5.3)
        """
        await self._ensure_token()
        session = self._get_session()
        all_params = dict(params or {})
        all_params["token"] = self._token
        try:
            async with session.get(
                f"{self._base_url}/{path}",
                params=all_params,
            ) as resp:
                if resp.status == 401:
                    self._token = None
                    raise RensonAuthError("Token rejected (401)")
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            raise RensonConnectionError(f"Request failed: {err}") from err

    async def get_gateway_serial(self) -> str:
        """Return the gateway serial number for use as unique device ID."""
        data = await self._get("get_status")
        return str(data.get("serial", ""))

    async def get_thermostat_status(self) -> ThermostatStatus:
        """Read thermostat group 1 status."""
        data = await self._get("get_thermostat_group_status")
        _LOGGER.debug("get_thermostat_group_status raw: %s", data)
        groups = data.get("status", [])
        # Group 0 has empty thermostats; find the first group that has thermostats
        group = next((g for g in groups if g.get("thermostats")), None)
        if not group:
            return ThermostatStatus(None, None, None, None, None)
        thermostat = group["thermostats"][0]
        return ThermostatStatus(
            actual_temperature=thermostat.get("actual_temperature"),
            setpoint=thermostat.get("setpoint_temperature"),
            active_preset=thermostat.get("preset"),
            mode=group.get("mode"),
            steering_power=thermostat.get("steering_power"),
        )

    async def get_output_status(self) -> dict[int, OutputStatus]:
        """Return status for all gateway outputs."""
        data = await self._get("get_output_status")
        _LOGGER.debug("get_output_status raw: %s", data)
        result: dict[int, OutputStatus] = {}
        for item in data.get("status", []):
            oid = item.get("id")
            if oid is None:
                continue
            result[oid] = OutputStatus(
                output_id=oid,
                status=item.get("status", 0),
                dimmer=item.get("dimmer"),
            )
        return result

    async def get_plugin_config(self) -> PluginConfig:
        """Return parsed config from the rensonheatpumplogic plugin."""
        data = await self._get("plugins/rensonheatpumplogic/get_config")
        _LOGGER.debug("get_config raw: %s", data)

        silent = next(iter(data.get("silent_mode_config") or []), {})
        hp = next(iter(data.get("heatpump_config") or []), {})
        state_cfg = next(iter(data.get("state_config") or []), {})

        return PluginConfig(
            silent_mode=silent.get("silent_mode") == "On",
            silent_mode_recurrent=silent.get("silent_mode_recurrent") == "On",
            silent_mode_start_hour=silent.get("silent_mode_start_hour"),
            silent_max_time=silent.get("silent_max_time"),
            silent_current_running_time=silent.get("current_running_time"),
            backup_heater=hp.get("backup_heater") == "On",
            type_energy_source=hp.get("type_energy_source"),
            state=state_cfg.get("state"),
            commissioning_state=state_cfg.get("commissioning_state"),
        )

    async def _set_plugin_section(self, section: str, updates: dict[str, Any]) -> None:
        """Read one config section, apply field updates, write it back."""
        data = await self._get("plugins/rensonheatpumplogic/get_config")
        entries: list[dict[str, Any]] = data.get(section, [])
        for entry in entries:
            entry.update(updates)
        await self._get(
            "plugins/rensonheatpumplogic/set_config",
            params={"config": json.dumps({section: entries})},
        )

    async def set_setpoint(self, temperature: float) -> None:
        """Write heating setpoint via Modbus register 20 (value = temperature × 10)."""
        value = int(round(temperature * 10))
        await self._get(
            "write_modbus_register",
            params={"slaveaddress": self._modbus_slave, "registeraddress": 20, "value": value},
        )

    async def set_preset(self, preset_value: int) -> None:
        """Write preset via Modbus register 3 (0=auto, 1=away, 5=manual)."""
        await self._get(
            "write_modbus_register",
            params={"slaveaddress": self._modbus_slave, "registeraddress": 3, "value": preset_value},
        )

    async def set_hvac_mode(self, mode: str) -> None:
        """Set thermostat group mode (heating or cooling)."""
        await self._get(
            "set_thermostat_group",
            params={"thermostat_group_id": 1, "mode": mode},
        )

    async def set_silent_mode(self, enabled: bool) -> None:
        """Enable or disable silent mode via rensonheatpumplogic plugin."""
        await self._set_plugin_section(
            "silent_mode_config", {"silent_mode": "On" if enabled else "Off"}
        )

    async def set_silent_mode_recurrent(self, enabled: bool) -> None:
        """Enable or disable recurring silent mode."""
        await self._set_plugin_section(
            "silent_mode_config", {"silent_mode_recurrent": "On" if enabled else "Off"}
        )

    async def set_backup_heater(self, enabled: bool) -> None:
        """Enable or disable the backup heater."""
        await self._set_plugin_section(
            "heatpump_config", {"backup_heater": "On" if enabled else "Off"}
        )
