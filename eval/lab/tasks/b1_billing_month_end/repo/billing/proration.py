from decimal import Decimal


def prorate(amount, period_start, period_end, change_date):
    """Share of `amount` for the remainder of the period from change_date."""
    total_days = (period_end - period_start).days
    remaining = (period_end - change_date).days
    return (Decimal(str(amount)) * remaining / total_days).quantize(Decimal("0.01"))
