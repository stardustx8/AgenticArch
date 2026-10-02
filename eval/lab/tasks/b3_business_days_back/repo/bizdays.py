import datetime

from calendars import BusinessCalendar

ONE_DAY = datetime.timedelta(days=1)


def add_business_days(start, n, calendar=None):
    # Move forward n business days from start. n == 0 returns start unchanged.
    calendar = calendar if calendar is not None else BusinessCalendar()
    if n < 0:
        raise ValueError('n must be non-negative')
    current = start
    remaining = n
    while remaining > 0:
        current += ONE_DAY
        if calendar.is_business_day(current):
            remaining -= 1
    return current


def business_days_between(start, end, calendar=None):
    # Number of business days in (start, end].
    calendar = calendar if calendar is not None else BusinessCalendar()
    count = 0
    current = start
    while current < end:
        current += ONE_DAY
        if calendar.is_business_day(current):
            count += 1
    return count
