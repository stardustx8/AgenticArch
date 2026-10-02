import json
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Event:
    user: str
    ts: datetime
    action: str


def parse_ts(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def parse_event(line):
    data = json.loads(line)
    return Event(data["user"], parse_ts(data["ts"]), data["action"])


def parse_events(lines):
    return [parse_event(line) for line in lines if line.strip()]
