def flatten(obj, sep=".", prefix=""):
    """Flatten nested dicts into a single-level dict with joined keys."""
    out = {}
    for key, value in obj.items():
        full = f"{prefix}{sep}{key}" if prefix else str(key)
        if isinstance(value, dict):
            out.update(flatten(value, sep, full))
        else:
            out[full] = value
    return out


def unflatten(flat, sep="."):
    """Rebuild nested dicts from a flattened dict."""
    root = {}
    for path, value in flat.items():
        parts = path.split(sep)
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return root
