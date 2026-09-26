from datetime import timezone

from .timeparse import parse_ts


def _instant(value):
    ts = parse_ts(value)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def dedupe_latest(rows, key="id", ts_field="updated_at"):
    """Collapse rows sharing the same key, keeping the most recently updated one.

    Timestamps are compared as instants (offsets respected, naive = UTC). On a
    tie the row appearing later in the input wins. The result keeps the order
    in which each key first appeared.
    """
    latest = {}
    for row in rows:
        k = row[key]
        ts = _instant(row[ts_field])
        current = latest.get(k)
        if current is None or ts >= current[0]:
            latest[k] = (ts, row)
    return [row for _, row in latest.values()]
