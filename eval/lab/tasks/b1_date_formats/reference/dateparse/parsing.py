import re
from datetime import date

_MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_EU_RE = re.compile(r"(\d{1,2})([/.])(\d{1,2})\2(\d{4})")
_US_RE = re.compile(r"([A-Za-z]+)\.? (\d{1,2}), (\d{4})")


def _month_number(name: str) -> int:
    key = name.lower()
    for number, full in enumerate(_MONTHS, start=1):
        if key == full or key == full[:3]:
            return number
    raise ValueError(f"unknown month name: {name!r}")


def parse_date(value: str) -> date:
    """Parse a date string coming from an import file.

    Accepts ISO ``2024-12-31``, day-first ``31/12/2024`` or ``31.12.2024`` and
    US-style ``Dec 31, 2024`` / ``December 31, 2024``. Raises ValueError otherwise.
    """
    if not isinstance(value, str):
        raise ValueError(f"expected a string, got {type(value).__name__}")
    text = value.strip()
    if _ISO_RE.fullmatch(text):
        return date.fromisoformat(text)
    m = _EU_RE.fullmatch(text)
    if m:
        day, _, month, year = m.groups()
        return date(int(year), int(month), int(day))
    m = _US_RE.fullmatch(text)
    if m:
        month_name, day, year = m.groups()
        return date(int(year), _month_number(month_name), int(day))
    raise ValueError(f"unrecognised date: {value!r}")
