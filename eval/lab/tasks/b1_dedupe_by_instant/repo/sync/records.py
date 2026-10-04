def dedupe_latest(rows, key="id", ts_field="updated_at"):
    """Collapse rows sharing the same key, keeping the most recently updated one."""
    seen = {}
    for row in rows:
        k = row[key]
        if k not in seen or row[ts_field] > seen[k][ts_field]:
            seen[k] = row
    return list(seen.values())
