def group_by(rows, keys):
    """Group rows by the named attributes; returns {value_tuple: [rows]}."""
    groups = {}
    for row in rows:
        key = tuple(getattr(row, k) for k in keys)
        groups.setdefault(key, []).append(row)
    return groups
