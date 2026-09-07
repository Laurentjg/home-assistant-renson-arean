"""Immediate confirmation after a write (§6.2, P-09).

Three mechanisms together. The optimistic value makes the UI react within a
frame. The accelerated refresh schedule asks the gateway again at 2, 5, 8, 12
and 20 seconds, because the app polls the thermostat every 5 s and the answer
cannot arrive sooner. And the fallback protection is the one 2026.6.0 lacked:
while the window is open, a poll carrying the old value does not overwrite what
the user just set — otherwise a poll landing just before the app's own cycle
undoes the change and the user turns the dial again.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

_LOGGER = logging.getLogger(__package__)

# Seconds after the write at which the gateway is asked again.
REFRESH_SCHEDULE = (2, 5, 8, 12, 20)
WINDOW = timedelta(seconds=REFRESH_SCHEDULE[-1] + 5)


@dataclass
class _Pending:
    value: Any
    deadline: datetime


class ConfirmationWindow:
    """Hold written values until the gateway confirms them, or time runs out."""

    def __init__(self, now: Callable[[], datetime] = datetime.now) -> None:
        """`now` is injectable so the window can be tested without waiting."""
        self._now = now
        self._pending: dict[str, _Pending] = {}

    def start(self, key: str, value: Any) -> None:
        """Record what was just written."""
        self._pending[key] = _Pending(value=value, deadline=self._now() + WINDOW)

    def pending(self, key: str) -> Any:
        """The optimistic value, or None once the window closed."""
        entry = self._pending.get(key)
        if entry is None:
            return None
        if self._now() > entry.deadline:
            del self._pending[key]
            _LOGGER.warning(
                "schrijfactie %s niet bevestigd door de gateway binnen %s s; "
                "de gatewaywaarde is weer leidend",
                key,
                int(WINDOW.total_seconds()),
            )
            return None
        return entry.value

    def resolve(self, key: str, reported: Any) -> Any:
        """Return the value to show, and close the window once it matches.

        This is the whole trick: as long as the gateway still reports the old
        value the written one stays on screen, and the moment it agrees the
        window closes early.
        """
        expected = self.pending(key)
        if expected is None:
            return reported
        if reported == expected:
            del self._pending[key]
            return reported
        return expected

    def is_open(self, key: str) -> bool:
        """True while a write is still awaiting confirmation."""
        return self.pending(key) is not None
