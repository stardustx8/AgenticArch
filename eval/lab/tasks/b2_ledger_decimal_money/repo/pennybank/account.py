from __future__ import annotations

from typing import NamedTuple

from .errors import InsufficientFunds

DEPOSIT = "deposit"
WITHDRAWAL = "withdrawal"


class Entry(NamedTuple):
    kind: str
    amount: float


class Account:
    """A single-currency account with an append-only history."""

    def __init__(self, owner: str) -> None:
        if not owner:
            raise ValueError("owner is required")
        self.owner = owner
        self._balance = 0.0
        self._history: list[Entry] = []

    def deposit(self, amount: float) -> float:
        amount = _validate(amount)
        self._balance += amount
        self._history.append(Entry(DEPOSIT, amount))
        return self._balance

    def withdraw(self, amount: float) -> float:
        amount = _validate(amount)
        if amount > self._balance:
            raise InsufficientFunds(amount, self._balance)
        self._balance -= amount
        self._history.append(Entry(WITHDRAWAL, amount))
        return self._balance

    def balance(self) -> float:
        return self._balance

    def history(self) -> list[Entry]:
        return list(self._history)

    def __repr__(self) -> str:
        return f"Account(owner={self.owner!r}, balance={self._balance:.2f})"


def _validate(amount: float) -> float:
    if not isinstance(amount, (int, float)):
        raise TypeError(f"amount must be a number, got {type(amount).__name__}")
    if amount <= 0:
        raise ValueError(f"amount must be positive, got {amount}")
    return float(amount)
