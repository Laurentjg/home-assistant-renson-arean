"""The two write paths of §5.4.

Reading always goes over the generic OpenMotics API, which is stable and
app-independent. Only writing is backend-specific, so the integration works on
a bare OpenMotics installation and still uses the Renson app where it exists.

There is deliberately no generic "write any Modbus register" primitive: as a
service that would be a remote arbitrary write onto the installation bus
(SEC-10). Values are range-checked before they reach the bus (SEC-12).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..const import (
    PRESET_TO_REGISTER,
    SETPOINT_MAX,
    SETPOINT_MIN,
)

if TYPE_CHECKING:
    from ..api.client import RensonClient
    from ..api.models import ThermostatAppConfig

# Registers of the wall thermostat on the Modbus RTU bus.
REGISTER_PRESET = 3
REGISTER_SETPOINT = 20


def validate_setpoint(temperature: float) -> float:
    """Return the setpoint, or raise ValueError if it is out of range."""
    if not SETPOINT_MIN <= temperature <= SETPOINT_MAX:
        raise ValueError(
            f"setpoint {temperature} ligt buiten {SETPOINT_MIN}-{SETPOINT_MAX} °C"
        )
    return temperature


def validate_preset(preset: str) -> int:
    """Return the register value for a preset, or raise ValueError."""
    if preset not in PRESET_TO_REGISTER:
        raise ValueError(f"onbekend preset {preset!r}")
    return PRESET_TO_REGISTER[preset]


class ThermostatBackend:
    """A way to write a setpoint and a preset."""

    name = "backend"

    async def set_setpoint(self, temperature: float) -> None:
        """Write the setpoint."""
        raise NotImplementedError

    async def set_preset(self, preset: str) -> None:
        """Write the preset."""
        raise NotImplementedError


class RensonModbusBackend(ThermostatBackend):
    """Write over Modbus to the wall thermostat — the proven 2026.6.0 path."""

    name = "renson_modbus"

    def __init__(self, client: RensonClient, slave: int) -> None:
        """Bind the backend to one Modbus slave."""
        self._client = client
        self._slave = slave

    async def set_setpoint(self, temperature: float) -> None:
        """Write register 20, which holds the setpoint times ten."""
        value = int(round(validate_setpoint(temperature) * 10))
        await self._client.write_thermostat_register(
            self._slave, REGISTER_SETPOINT, value
        )

    async def set_preset(self, preset: str) -> None:
        """Write register 3."""
        await self._client.write_thermostat_register(
            self._slave, REGISTER_PRESET, validate_preset(preset)
        )


class OpenMoticsBackend(ThermostatBackend):
    """Write over the generic OpenMotics API.

    Used when the Renson app is absent or reports no Modbus binding. Never
    exercised against this gateway (V-14): confirming it requires a write.
    """

    name = "openmotics"

    def __init__(self, client: RensonClient, thermostat_id: int) -> None:
        """Bind the backend to one OpenMotics thermostat."""
        self._client = client
        self._thermostat_id = thermostat_id

    async def set_setpoint(self, temperature: float) -> None:
        """Write the setpoint over set_current_setpoint."""
        await self._client.set_current_setpoint(
            self._thermostat_id, validate_setpoint(temperature)
        )

    async def set_preset(self, preset: str) -> None:
        """The generic API has no preset concept, so this path stays closed."""
        raise NotImplementedError(
            "presets zijn alleen te schrijven via de RensonThermostat-app"
        )


def select_backend(
    client: RensonClient,
    thermostat_id: int,
    app_config: ThermostatAppConfig | None,
) -> ThermostatBackend:
    """Pick the write path: the Renson app where it binds this thermostat."""
    if app_config is not None:
        slave = app_config.bindings.get(thermostat_id)
        if slave is not None:
            return RensonModbusBackend(client, slave)
    return OpenMoticsBackend(client, thermostat_id)
