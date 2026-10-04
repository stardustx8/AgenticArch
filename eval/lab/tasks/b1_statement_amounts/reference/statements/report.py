from collections import defaultdict
from decimal import Decimal


def monthly_summary(transactions):
    """Total amount per (month 'YYYY-MM', currency)."""
    totals = defaultdict(Decimal)
    for t in transactions:
        totals[(t.date.strftime("%Y-%m"), t.currency)] += t.amount
    return dict(totals)


def format_summary(summary):
    lines = []
    for month, currency in sorted(summary):
        lines.append(f"{month} {currency}: {summary[(month, currency)]:.2f}")
    return "\n".join(lines)
