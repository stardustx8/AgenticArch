import re
from dataclasses import dataclass

LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\] (.*)$")


@dataclass(frozen=True)
class LogEntry:
    timestamp: str
    level: str
    message: str


def parse_line(line):
    m = LINE_RE.match(line.rstrip("\n"))
    if not m:
        return None
    return LogEntry(*m.groups())


def parse_lines(lines):
    return [e for e in (parse_line(line) for line in lines) if e is not None]
