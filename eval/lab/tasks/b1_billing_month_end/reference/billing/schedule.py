from datetime import date

from .periods import add_months


def billing_schedule(anchor: date, count: int):
    """Return `count` consecutive (start, end) billing periods, end exclusive.

    Every boundary is computed from the anchor, so a subscription started on
    the 31st bills on the last day of shorter months and returns to the 31st.
    """
    return [(add_months(anchor, i), add_months(anchor, i + 1)) for i in range(count)]


def current_period(anchor: date, on_date: date):
    """Return the (start, end) billing period containing on_date, end exclusive."""
    if on_date < anchor:
        raise ValueError(f"{on_date} is before the subscription anchor {anchor}")
    i = (on_date.year - anchor.year) * 12 + (on_date.month - anchor.month)
    while i > 0 and add_months(anchor, i) > on_date:
        i -= 1
    while add_months(anchor, i + 1) <= on_date:
        i += 1
    return add_months(anchor, i), add_months(anchor, i + 1)
