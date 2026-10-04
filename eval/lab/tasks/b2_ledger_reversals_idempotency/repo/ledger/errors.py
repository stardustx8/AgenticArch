class LedgerError(Exception):
    """Base class for every error raised by the ledger."""


class UnknownAccount(LedgerError):
    """No account with the given name exists."""


class DuplicateAccount(LedgerError):
    """An account with the given name is already open."""


class UnknownTransaction(LedgerError):
    """No transaction with the given id exists."""


class InvalidAmount(LedgerError, ValueError):
    """Amounts must be positive integers (cents)."""


class InsufficientFunds(LedgerError):
    """The source account cannot cover the transfer."""
