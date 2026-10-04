from datetime import date

from .periods import add_months


def billing_schedule(anchor: date, count: int):
    """Return `count` consecutive (start, end) billing periods, end exclusive."""
    periods = []
    start = anchor
    for _ in range(count):
        end = add_months(start, 1)
        periods.append((start, end))
        start = end
    return periods
