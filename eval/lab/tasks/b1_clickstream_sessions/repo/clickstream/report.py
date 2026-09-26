def summarize(sessions):
    """Per-user totals: number of sessions, number of actions, seconds spent."""
    out = {}
    for s in sessions:
        stats = out.setdefault(s.user, {"sessions": 0, "actions": 0, "seconds": 0})
        stats["sessions"] += 1
        stats["actions"] += len(s.actions)
        stats["seconds"] += s.duration_seconds
    return out
