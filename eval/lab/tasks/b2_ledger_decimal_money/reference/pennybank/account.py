from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import NamedTuple

from .errors import InsufficientFunds

DEPOSIT = "deposit"
WITHDRAWAL = "withdrawal"
CENT = Decimal("0.01")

Amount = Decimal | int | str


class Entry(NamedTuple):
    kind: str
    amount: Decimal


class Account:
    """A single-currency account with an append-only history."""

    def __init__(self, owner: str) -> None:
        if not owner:
            raise ValueError("owner is required")
        self.owner = owner
        self._balance = Decimal("0.00")
        self._history: list[Entry] = []

    def deposit(self, amount: Amount) -> Decimal:
        value = _to_money(amount)
        self._balance += value
        self._history.append(Entry(DEPOSIT, value))
        return self._balance

    def withdraw(self, amount: Amount) -> Decimal:
        value = _to_money(amount)
        if value > self._balance:
            raise InsufficientFunds(value, self._balance)
        self._balance -= value
        self._history.append(Entry(WITHDRAWAL, value))
        return self._balance

    def balance(self) -> Decimal:
        return self._balance

    def history(self) -> list[Entry]:
        return list(self._history)

    def __repr__(self) -> str:
        return f"Account(owner={self.owner!r}, balance={self._balance})"


def _to_money(amount: Amount) -> Decimal:
    """Convert *amount* to a positive Decimal with exactly two places."""
    if isinstance(amount, float):
        raise TypeError("floats are not accepted as money; pass a Decimal, int or str")
    if not isinstance(amount, (Decimal, int, str)):
        raise TypeError(f"amount must be a Decimal, int or str, got {type(amount).__name__}")
    try:
        value = Decimal(amount)
    except InvalidOperation:
        raise ValueError(f"not a valid amount: {amount!r}") from None
    if not value.is_finite():
        raise ValueError(f"amount must be finite, got {amount!r}")
    if value <= 0:
        raise ValueError(f"amount must be positive, got {amount!r}")
    cents = value.quantize(CENT)
    if cents != value:
        raise ValueError(f"amount has more than two decimal places: {amount!r}")
    return cents
