import calendar
from datetime import date


def days_in_month(year, month):
    return calendar.monthrange(year, month)[1]


def add_months(d: date, n: int, anchor_day: int | None = None) -> date:
    """Shift a date by n calendar months.

    The day is clamped to the last day of the target month. Pass `anchor_day`
    to aim for a specific day of month instead of d.day.
    """
    month_index = d.month - 1 + n
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(anchor_day or d.day, days_in_month(year, month))
    return date(year, month, day)
