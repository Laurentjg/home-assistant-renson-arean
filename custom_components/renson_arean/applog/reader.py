"""Turn the `get_plugin_logs` response into log lines per app.

This half is deliberately dumb: it splits and it timestamps, it interprets
nothing. The buffer holds exactly 100 lines per app — roughly 1.5 minutes for
`rensonheatpumplogic` — which is why it is polled every 30 s (CN-11, §6.2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

LINE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?)"
    r" - (?P<level>[A-Z]+) - (?P<message>.*)$"
)


@dataclass(frozen=True)
class LogLine:
    """One line from an app log."""

    timestamp: datetime | None
    level: str
    message: str


def _timestamp(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_logs(raw: dict[str, Any]) -> dict[str, list[LogLine]]:
    """Split the response into log lines per app.

    A line that does not match the expected shape is kept with an empty level
    rather than dropped: the next line may need it as context, and silently
    losing log content is worse than carrying a stray line along.
    """
    logs: dict[str, list[LogLine]] = {}
    for app, text in (raw.get("logs") or {}).items():
        if not isinstance(text, str):
            continue
        lines: list[LogLine] = []
        for line in text.split("\n"):
            if not line.strip():
                continue
            match = LINE.match(line)
            if match:
                lines.append(
                    LogLine(
                        timestamp=_timestamp(match.group("timestamp")),
                        level=match.group("level"),
                        message=match.group("message"),
                    )
                )
            else:
                lines.append(LogLine(timestamp=None, level="", message=line.strip()))
        logs[app] = lines
    return logs
