def _normalize(value):
    return value.strip().casefold() if isinstance(value, str) else value


def _label(value):
    return value.strip() if isinstance(value, str) else value


def group_by(rows, keys):
    """Group rows by the named attributes; returns {label_tuple: [rows]}.

    Values that differ only in case or surrounding whitespace share a group,
    labelled with the first spelling seen (trimmed). Groups come back ordered
    by their case-insensitive key.
    """
    labels = {}
    groups = {}
    for row in rows:
        values = [getattr(row, k) for k in keys]
        norm = tuple(_normalize(v) for v in values)
        if norm not in groups:
            labels[norm] = tuple(_label(v) for v in values)
            groups[norm] = []
        groups[norm].append(row)
    return {labels[norm]: groups[norm] for norm in sorted(groups)}
