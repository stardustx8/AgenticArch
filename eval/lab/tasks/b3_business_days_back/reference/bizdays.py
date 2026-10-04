import datetime

from calendars import BusinessCalendar

ONE_DAY = datetime.timedelta(days=1)


def add_business_days(start, n, calendar=None):
    # Move n business days from start, backwards when n < 0.
    # n == 0 returns start unchanged, even on a weekend or holiday.
    calendar = calendar if calendar is not None else BusinessCalendar()
    step = ONE_DAY if n > 0 else -ONE_DAY
    current = start
    remaining = abs(n)
    while remaining > 0:
        current += step
        if calendar.is_business_day(current):
            remaining -= 1
    return current


def business_days_between(start, end, calendar=None):
    # Business days in (start, end] when end >= start. When end < start, minus the
    # business days in [end, start), so add_business_days(start, result) == end
    # whenever end is a business day.
    calendar = calendar if calendar is not None else BusinessCalendar()
    count = 0
    if end >= start:
        current = start
        while current < end:
            current += ONE_DAY
            if calendar.is_business_day(current):
                count += 1
        return count
    current = end
    while current < start:
        if calendar.is_business_day(current):
            count += 1
        current += ONE_DAY
    return -count
