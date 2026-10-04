from __future__ import annotations

from .errors import (
    DuplicateAccount,
    InsufficientFunds,
    InvalidAmount,
    LedgerError,
    UnknownAccount,
    UnknownTransaction,
)
from .models import Account, Transaction


class Ledger:
    """In-memory ledger; balances are integer cents and never go negative."""

    def __init__(self) -> None:
        self._accounts: dict[str, Account] = {}
        self._transactions: dict[str, Transaction] = {}
        self._next_id = 1

    def open_account(self, name: str, initial_cents: int = 0) -> None:
        if name in self._accounts:
            raise DuplicateAccount(name)
        if isinstance(initial_cents, bool) or not isinstance(initial_cents, int) or initial_cents < 0:
            raise InvalidAmount(f"invalid opening balance: {initial_cents!r}")
        self._accounts[name] = Account(name, initial_cents)

    def balance(self, name: str) -> int:
        return self._account(name).balance

    def accounts(self) -> list[str]:
        return sorted(self._accounts)

    def transfer(self, src: str, dst: str, amount_cents: int, memo: str = "") -> str:
        _check_amount(amount_cents)
        if src == dst:
            raise LedgerError("cannot transfer to the same account")
        source = self._account(src)
        dest = self._account(dst)
        _check_funds(source, amount_cents)
        return self._post(source, dest, amount_cents, memo)

    def transaction(self, txn_id: str) -> Transaction:
        try:
            return self._transactions[txn_id]
        except KeyError:
            raise UnknownTransaction(txn_id) from None

    def history(self, name: str) -> list[Transaction]:
        self._account(name)
        return [t for t in self._transactions.values() if t.involves(name)]

    def _post(self, source: Account, dest: Account, amount: int, memo: str) -> str:
        txn = Transaction(f"t{self._next_id}", source.name, dest.name, amount, memo)
        self._next_id += 1
        source.balance -= amount
        dest.balance += amount
        self._transactions[txn.id] = txn
        return txn.id

    def _account(self, name: str) -> Account:
        try:
            return self._accounts[name]
        except KeyError:
            raise UnknownAccount(name) from None


def _check_amount(amount: object) -> None:
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise InvalidAmount(f"amount must be a positive number of cents, got {amount!r}")


def _check_funds(account: Account, amount: int) -> None:
    if account.balance < amount:
        raise InsufficientFunds(f"{account.name} has {account.balance}, needs {amount}")
