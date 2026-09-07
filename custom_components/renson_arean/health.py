"""Source health tracking (§7.2).

The rule this module exists for: log the complete picture once at startup, then
say nothing until something actually changes. An integration that repeats
"source missing" every ten seconds makes the log useless and hides the moment
it first went wrong.

Free of Home Assistant imports so the state machine can be tested on its own.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

_LOGGER = logging.getLogger(__package__)

STATUS_OK = "OK"
STATUS_ERROR = "FOUT"
STATUS_MISSING = "ONTBREEKT"
STATUS_INVALID = "ONGELDIG"

# Only a failure line carries this marker: it tells the reader the fault
# persists even though the log stays quiet. On an OK or recovery line the
# marker would be the noise it is meant to prevent.
QUIET_MARKER = "next log-message at change only"


@dataclass(frozen=True)
class SourceState:
    """What a source last reported."""

    status: str
    reason: str | None
    since: datetime

    @property
    def healthy(self) -> bool:
        """True while the source delivers data."""
        return self.status == STATUS_OK


class SourceHealthTracker:
    """Remember the last state per source and log only transitions."""

    def __init__(self, now=datetime.now) -> None:
        """`now` is injectable so the duration of an outage can be tested."""
        self._now = now
        self._states: dict[str, SourceState] = {}
        self._started = False

    @property
    def states(self) -> dict[str, SourceState]:
        """The current state of every known source."""
        return dict(self._states)

    def report(self, source: str, status: str, reason: str | None = None) -> None:
        """Record what one source reported this cycle.

        Logs on the first report, on a change of status, and on a change of
        reason within the same failure — a 404 turning into a timeout is new
        information. Otherwise it stays silent, however long the fault lasts.
        """
        now = self._now()
        previous = self._states.get(source)
        self._states[source] = SourceState(status=status, reason=reason, since=now)

        if previous is None:
            if self._started:
                self._log(source, status, reason)
            return

        if previous.status == status and previous.reason == reason:
            # Keep the original start time: an outage that continues has not
            # restarted, and its duration must stay measurable.
            self._states[source] = SourceState(
                status=status, reason=reason, since=previous.since
            )
            return

        if status == STATUS_OK and not previous.healthy:
            self._log(source, status, reason, recovered_after=now - previous.since)
            return

        self._log(source, status, reason)

    def log_startup_summary(self) -> None:
        """Write one line per source plus a summary — the complete start picture."""
        for source, state in sorted(self._states.items()):
            self._log(source, state.status, state.reason)

        counts: dict[str, int] = {}
        for state in self._states.values():
            counts[state.status] = counts.get(state.status, 0) + 1
        _LOGGER.info(
            "bronnen bij start: %s",
            ", ".join(f"{status}={count}" for status, count in sorted(counts.items()))
            or "geen",
        )
        self._started = True

    def _log(
        self,
        source: str,
        status: str,
        reason: str | None,
        recovered_after: timedelta | None = None,
    ) -> None:
        if recovered_after is not None:
            _LOGGER.info(
                "bron=%s status=HERSTELD na %s", source, _duration(recovered_after)
            )
            return
        if status == STATUS_OK:
            _LOGGER.info("bron=%s status=%s%s", source, status, _suffix(reason))
            return
        _LOGGER.warning(
            "bron=%s status=%s%s — %s", source, status, _suffix(reason), QUIET_MARKER
        )


def _suffix(reason: str | None) -> str:
    return f" {reason}" if reason else ""


def _duration(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
