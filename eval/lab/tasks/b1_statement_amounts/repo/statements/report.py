from collections import defaultdict
from decimal import Decimal


def monthly_summary(transactions):
    """Total amount per month ('YYYY-MM')."""
    totals = defaultdict(Decimal)
    for t in transactions:
        totals[t.date.strftime("%Y-%m")] += t.amount
    return dict(totals)


def format_summary(summary):
    lines = []
    for month in sorted(summary):
        lines.append(f"{month}: {summary[month]:.2f}")
    return "\n".join(lines)
