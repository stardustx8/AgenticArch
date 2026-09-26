import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .amounts import parse_amount


@dataclass(frozen=True)
class Transaction:
    date: date
    description: str
    amount: Decimal
    currency: str


def load_transactions(text):
    """Load transactions from statement CSV text (date,description,amount,currency).

    Rows without an amount (e.g. pending transactions) are skipped.
    """
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        raw_amount = (row.get("amount") or "").strip()
        if not raw_amount:
            continue
        out.append(
            Transaction(
                date.fromisoformat(row["date"].strip()),
                row["description"],
                parse_amount(raw_amount),
                row["currency"].strip().upper(),
            )
        )
    return out
