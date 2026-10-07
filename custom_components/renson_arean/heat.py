"""Heat output and heat energy, derived from the water side of the heat pump.

Free of Home Assistant imports, so the arithmetic can be tested without a
Home Assistant runtime.

Both are derived values, not measurements: the heat pump reports no heat
output. What it does report is the flow and the temperature on both sides of
the plate heat exchanger, and the heat the water carries away follows from
those. No electrical quantity is derived here, and no COP: that needs a
meter the installation does not have.
"""

from __future__ import annotations

from typing import Any


def _number(value: Any) -> float | None:
    """A measured number, or None for anything else the log may hold."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def heat_output(flow: Any, supply: Any, ret: Any, factor: float) -> float | None:
    """Heat given to the water, in kW.

    `flow` in m³/h, `supply` and `ret` in °C, `factor` in kWh/(m³·K). The
    sign is kept: while defrosting or cooling the water returns warmer than it
    leaves, and the heat pump takes heat out of the system.
    """
    flow, supply, ret = _number(flow), _number(supply), _number(ret)
    if flow is None or supply is None or ret is None:
        return None
    # `+ 0.0` turns a negative zero into a plain one.
    return flow * factor * (supply - ret) + 0.0


class HeatEnergyCounter:
    """Add up heat output over time, in kWh.

    The heat pump values are logged when they change, so a value holds until
    the next one: each interval counts with the output at its *start*.

    An interval longer than `max_gap` seconds is not counted at all. That is
    a restart or an outage, and what the heat pump did meanwhile is unknown;
    inventing it would be worse than missing it.
    """

    def __init__(self, total: float = 0.0, max_gap: float = 300.0) -> None:
        """Start from `total` kWh, with no previous sample."""
        self.total = total
        self._max_gap = max_gap
        self._power: float | None = None
        self._time: float | None = None

    @property
    def counting(self) -> bool:
        """Whether the last sample had a value to count from."""
        return self._power is not None

    def add(self, power: float | None, now: float) -> None:
        """Take one sample: `power` in kW at `now`, in seconds on any steady clock."""
        if self._power is not None and self._time is not None:
            elapsed = now - self._time
            if 0 < elapsed <= self._max_gap:
                self.total += self._power * elapsed / 3600
        self._power = power
        self._time = now
