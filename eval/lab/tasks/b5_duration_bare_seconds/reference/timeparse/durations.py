import re

_UNITS = {'d': 86400, 'h': 3600, 'm': 60, 's': 1}
_TOKEN = re.compile(r'([0-9]+)([dhms])')


def parse_duration(text):
    """Parse a duration like '1h30m', '45s' or '2d' into seconds.

    A bare number is interpreted as seconds.
    """
    cleaned = text.strip().lower()
    if not cleaned:
        raise ValueError('empty duration')
    if cleaned.isdigit():
        return int(cleaned)
    total = 0
    pos = 0
    for match in _TOKEN.finditer(cleaned):
        if match.start() != pos:
            raise ValueError(f'bad duration: {text!r}')
        total += int(match.group(1)) * _UNITS[match.group(2)]
        pos = match.end()
    if pos != len(cleaned):
        raise ValueError(f'bad duration: {text!r}')
    return total


def format_duration(seconds):
    """Format seconds as a compact duration string, e.g. 5400 -> '1h30m'."""
    if seconds < 0:
        raise ValueError('negative duration')
    if seconds == 0:
        return '0s'
    parts = []
    for unit, size in _UNITS.items():
        count, seconds = divmod(seconds, size)
        if count:
            parts.append(f'{count}{unit}')
    return ''.join(parts)
