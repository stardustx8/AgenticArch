from datetime import datetime


def parse_ts(value: str) -> datetime:
    """Parse an ISO 8601 timestamp (a trailing 'Z' means UTC)."""
    return datetime.fromisoformat(value)
