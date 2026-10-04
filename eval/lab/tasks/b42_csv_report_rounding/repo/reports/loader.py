import csv
import datetime
from dataclasses import dataclass
from decimal import Decimal

from .money import parse_amount

REQUIRED = ('date', 'region', 'category', 'amount', 'currency')


class LoadError(ValueError):
    pass


@dataclass(frozen=True)
class Transaction:
    date: datetime.date
    region: str
    category: str
    amount: Decimal
    currency: str


def load_transactions(lines):
    """Read transactions from CSV lines (an open file or a list of strings) with a header row."""
    reader = csv.DictReader(lines)
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        names = ', '.join(missing)
        raise LoadError(f'missing columns: {names}')
    rows = []
    for lineno, rec in enumerate(reader, start=2):
        try:
            rows.append(Transaction(
                date=datetime.date.fromisoformat(rec['date'].strip()),
                region=rec['region'],
                category=rec['category'],
                amount=parse_amount(rec['amount']),
                currency=rec['currency'].strip().upper(),
            ))
        except ValueError as exc:
            raise LoadError(f'line {lineno}: {exc}') from None
    return rows
