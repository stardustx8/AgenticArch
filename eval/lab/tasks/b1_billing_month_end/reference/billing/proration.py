from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def prorate(amount, period_start, period_end, change_date):
    """Share of `amount` for the remainder of the period from change_date.

    A change on/before the start yields the full amount, on/after the end
    yields zero. The result is rounded half-up to cents.
    """
    total_days = (period_end - period_start).days
    if total_days <= 0:
        raise ValueError("billing period must have a positive length")
    effective = min(max(change_date, period_start), period_end)
    remaining = (period_end - effective).days
    value = Decimal(str(amount)) * remaining / total_days
    return value.quantize(CENT, rounding=ROUND_HALF_UP)
