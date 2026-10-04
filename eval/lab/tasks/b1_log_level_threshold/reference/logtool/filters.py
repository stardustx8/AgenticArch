LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
ALIASES = {"WARN": "WARNING", "FATAL": "CRITICAL"}


def normalize_level(level):
    """Return the canonical level name, or None if the level is unknown."""
    name = str(level).strip().upper()
    name = ALIASES.get(name, name)
    return name if name in LEVELS else None


def filter_by_level(entries, min_level):
    """Keep entries at min_level or more severe, in their original order."""
    canonical = normalize_level(min_level)
    if canonical is None:
        raise ValueError(f"unknown log level: {min_level!r}")
    threshold = LEVELS[canonical]
    result = []
    for e in entries:
        level = normalize_level(e.level)
        if level is not None and LEVELS[level] >= threshold:
            result.append(e)
    return result


def filter_by_text(entries, needle):
    return [e for e in entries if needle in e.message]
