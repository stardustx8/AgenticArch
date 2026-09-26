import json
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Event:
    user: str
    ts: datetime
    action: str


def parse_ts(value):
    """Parse an ISO 8601 timestamp into an aware UTC datetime (naive = UTC)."""
    if not isinstance(value, str):
        raise ValueError(f"timestamp must be a string, got {value!r}")
    ts = datetime.fromisoformat(value)
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def parse_event(line):
    data = json.loads(line)
    if not isinstance(data, dict):
        raise ValueError("event must be a JSON object")
    return Event(data["user"], parse_ts(data["ts"]), data["action"])


def parse_events(lines, errors=None):
    """Parse JSON-lines events, skipping blank and malformed lines.

    If `errors` is a list, the 1-based line numbers of malformed lines are
    appended to it.
    """
    events = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            events.append(parse_event(line))
        except (ValueError, KeyError, TypeError):
            if errors is not None:
                errors.append(number)
    return events
