def flatten(obj, sep=".", prefix=""):
    """Flatten nested dicts/lists into a single-level dict with joined keys.

    List elements use their index as the key segment. Empty dicts and lists
    are kept as leaf values so nothing is lost.
    """
    out = {}
    items = obj.items() if isinstance(obj, dict) else enumerate(obj)
    for key, value in items:
        full = f"{prefix}{sep}{key}" if prefix else str(key)
        if isinstance(value, (dict, list)) and value:
            out.update(flatten(value, sep, full))
        else:
            out[full] = value
    return out


def unflatten(flat, sep="."):
    """Inverse of flatten(): rebuild nested dicts, turning levels whose keys
    are exactly 0..n-1 back into lists."""
    root = {}
    for path, value in flat.items():
        parts = path.split(sep)
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return _restore_lists(root)


def _restore_lists(node):
    if not isinstance(node, dict) or not node:
        return node
    rebuilt = {key: _restore_lists(value) for key, value in node.items()}
    if set(rebuilt) == {str(i) for i in range(len(rebuilt))}:
        return [rebuilt[str(i)] for i in range(len(rebuilt))]
    return rebuilt
