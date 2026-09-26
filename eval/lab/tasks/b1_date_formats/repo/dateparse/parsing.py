from datetime import date


def parse_date(value: str) -> date:
    """Parse a date string coming from an import file."""
    return date.fromisoformat(value)
