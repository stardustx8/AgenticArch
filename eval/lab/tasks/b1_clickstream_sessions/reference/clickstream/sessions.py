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
    """Group events into per-user sessions split by inactivity gaps.

    Events may arrive in any order. A new session starts when more than
    `gap_minutes` pass between consecutive events of the same user. Sessions
    are returned ordered by start time, then user.
    """
    gap = timedelta(minutes=gap_minutes)
    open_sessions = {}
    result = []
    for ev in sorted(events, key=lambda e: e.ts):
        s = open_sessions.get(ev.user)
        if s is None or ev.ts - s.end > gap:
            s = Session(ev.user, ev.ts, ev.ts, [ev.action])
            open_sessions[ev.user] = s
            result.append(s)
        else:
            s.end = ev.ts
            s.actions.append(ev.action)
    result.sort(key=lambda s: (s.start, s.user))
    return result
