from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class Session:
    user: str
    start: datetime
    end: datetime
    actions: list = field(default_factory=list)

    @property
    def duration_seconds(self):
        return int((self.end - self.start).total_seconds())


def sessionize(events, gap_minutes=30):
    """Group events into per-user sessions split by inactivity gaps."""
    gap = timedelta(minutes=gap_minutes)
    open_sessions = {}
    result = []
    for ev in events:
        s = open_sessions.get(ev.user)
        if s is None or ev.ts - s.end >= gap:
            s = Session(ev.user, ev.ts, ev.ts, [ev.action])
            open_sessions[ev.user] = s
            result.append(s)
        else:
            s.end = ev.ts
            s.actions.append(ev.action)
    return result
