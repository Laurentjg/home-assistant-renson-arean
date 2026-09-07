"""Interpret the log lines of `rensonheatpumplogic` (D-14).

This is the brittle half. The SSR arrays are unnamed and positional, and the
app rewrote them between versions — on 2026-06-26 `HP_UNIT/hp1` held 22 values,
on 2026-09-06 it held 25. So the layout is keyed to the app version, and an app
version this module does not know yields nothing at all rather than a value
that looks right and is not.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

from ..const import MODBUS_SENTINEL, SSR_ARRAYS, SSR_APP_VERSION
from .reader import LogLine

STATUS_CHANGED = re.compile(r"^SSR: Status changed for '(?P<key>[^']+)':$")
NEW_VALUES = re.compile(r"^SSR:\s+new:\s+(?P<array>\[.*\])$")
FORCED_REPORT = re.compile(
    r"^SSR: Forced report for '(?P<key>[^']+)':\s+(?P<array>\[.*\])$"
)
WEATHER = re.compile(r"^\s*Weather temperature:\s*(?P<value>-?\d+(?:\.\d+)?)\s*$")
BYPASS = re.compile(r"^BYPASS: current state = BypassState\.(?P<state>\w+)\s*$")

# `RensonHeatPumpR290` reports its hardware coupling in plain sentences (§5.7).
MODBUS_FAILURE = "Could not enable Modbus"
WATCHDOG_RESTART = "[Watchdog] Restarting runner"


@dataclass(frozen=True)
class SsrSnapshot:
    """Everything one poll of the log yielded."""

    arrays: dict[str, list[Any]] = field(default_factory=dict)
    weather_temperature: float | None = None
    bypass_state: str | None = None
    # Why an array was discarded — one line per reason, for the health tracker.
    rejected: tuple[str, ...] = ()

    def value(self, array_key: str, index: int) -> Any:
        """Return one position, or None when the array is absent or too short."""
        values = self.arrays.get(array_key)
        if values is None or index >= len(values):
            return None
        return values[index]


def _literal(text: str) -> list[Any] | None:
    """Parse a Python list literal, or return None if it is not one."""
    try:
        value = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None
    return value if isinstance(value, list) else None


def _clean(values: list[Any]) -> list[Any]:
    """Replace the Modbus "not available" sentinel by None (S-01, §7.3)."""
    return [None if value == MODBUS_SENTINEL else value for value in values]


def parse_ssr(lines: list[LogLine], app_version: str | None) -> SsrSnapshot:
    """Interpret the log of `rensonheatpumplogic`.

    An unknown app version yields an empty snapshot with a reason, so the
    entities that depend on it go unavailable instead of reporting a value from
    a layout that may have shifted (D-14 d).
    """
    if app_version != SSR_APP_VERSION:
        return SsrSnapshot(
            rejected=(
                f"app-versie {app_version!r} is onbekend; de positieafbeelding "
                f"is vastgesteld op {SSR_APP_VERSION}",
            ),
        )

    arrays: dict[str, list[Any]] = {}
    rejected: list[str] = []
    weather: float | None = None
    bypass: str | None = None
    pending_key: str | None = None

    def accept(key: str, values: list[Any]) -> None:
        layout = SSR_ARRAYS.get(key)
        if layout is None:
            rejected.append(f"onbekende SSR-array {key!r}")
            return
        if len(values) != layout.length:
            rejected.append(
                f"{key} heeft {len(values)} waarden, verwacht {layout.length}"
            )
            return
        arrays[key] = _clean(values)

    for line in lines:
        message = line.message

        changed = STATUS_CHANGED.match(message)
        if changed:
            pending_key = changed.group("key")
            continue

        new_values = NEW_VALUES.match(message)
        if new_values:
            values = _literal(new_values.group("array"))
            if pending_key and values is not None:
                accept(pending_key, values)
            pending_key = None
            continue

        forced = FORCED_REPORT.match(message)
        if forced:
            values = _literal(forced.group("array"))
            if values is not None:
                accept(forced.group("key"), values)
            continue

        weather_match = WEATHER.match(message)
        if weather_match:
            weather = float(weather_match.group("value"))
            continue

        bypass_match = BYPASS.match(message)
        if bypass_match:
            bypass = bypass_match.group("state")

    return SsrSnapshot(
        arrays=arrays,
        weather_temperature=weather,
        bypass_state=bypass,
        rejected=tuple(dict.fromkeys(rejected)),
    )


@dataclass(frozen=True)
class AppHealth:
    """What an app's own log says about its hardware coupling (§7.2)."""

    modbus_ok: bool | None = None
    watchdog_restarts: int = 0
    reason: str | None = None


def parse_app_health(lines: list[LogLine]) -> AppHealth:
    """Read the Modbus and watchdog state out of an app log.

    Returns `modbus_ok=None` when the log says nothing either way — silence is
    not evidence of health, and pretending otherwise would hide the failure
    this entity exists to show.
    """
    modbus_ok: bool | None = None
    restarts = 0
    reason: str | None = None

    for line in lines:
        if MODBUS_FAILURE in line.message:
            modbus_ok = False
            reason = line.message
        if WATCHDOG_RESTART in line.message:
            restarts += 1

    return AppHealth(modbus_ok=modbus_ok, watchdog_restarts=restarts, reason=reason)
