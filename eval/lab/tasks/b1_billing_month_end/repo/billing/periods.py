import calendar
from datetime import date


def days_in_month(year, month):
    return calendar.monthrange(year, month)[1]


def add_months(d: date, n: int) -> date:
    """Shift a date by n calendar months."""
    month_index = d.month - 1 + n
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return d.replace(year=year, month=month)
