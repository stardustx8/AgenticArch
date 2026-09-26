from __future__ import annotations

from .errors import (
    DuplicateAccount,
    IdempotencyConflict,
    InsufficientFunds,
    InvalidAmount,
    LedgerError,
    ReversalError,
    UnknownAccount,
    UnknownTransaction,
)
from .models import Account, Transaction

_Request = tuple[str, str, int, str]


class Ledger:
    """In-memory ledger; balances are integer cents and never go negative."""

    def __init__(self) -> None:
        self._accounts: dict[str, Account] = {}
        self._transactions: dict[str, Transaction] = {}
        self._next_id = 1
        self._idempotency: dict[str, tuple[_Request, str]] = {}
        self._reversed_by: dict[str, str] = {}
        self._reversal_of: dict[str, str] = {}

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

    def transfer(
        self,
        src: str,
        dst: str,
        amount_cents: int,
        memo: str = "",
        idempotency_key: str | None = None,
    ) -> str:
        request = (src, dst, amount_cents, memo)
        if idempotency_key is not None and idempotency_key in self._idempotency:
            seen, txn_id = self._idempotency[idempotency_key]
            if seen != request:
                raise IdempotencyConflict(
                    f"idempotency key {idempotency_key!r} was already used for a different transfer"
                )
            return txn_id
        _check_amount(amount_cents)
        if src == dst:
            raise LedgerError("cannot transfer to the same account")
        source = self._account(src)
        dest = self._account(dst)
        _check_funds(source, amount_cents)
        txn_id = self._post(source, dest, amount_cents, memo)
        if idempotency_key is not None:
            self._idempotency[idempotency_key] = (request, txn_id)
        return txn_id

    def reverse(self, txn_id: str) -> str:
        """Post a transfer undoing ``txn_id`` and return the new transaction id."""
        original = self.transaction(txn_id)
        if txn_id in self._reversal_of:
            raise ReversalError(f"{txn_id} is a reversal and cannot itself be reversed")
        if txn_id in self._reversed_by:
            raise ReversalError(f"{txn_id} was already reversed by {self._reversed_by[txn_id]}")
        source = self._account(original.dst)
        dest = self._account(original.src)
        _check_funds(source, original.amount)
        reversal_id = self._post(source, dest, original.amount, f"reversal of {txn_id}")
        self._reversed_by[txn_id] = reversal_id
        self._reversal_of[reversal_id] = txn_id
        return reversal_id

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
