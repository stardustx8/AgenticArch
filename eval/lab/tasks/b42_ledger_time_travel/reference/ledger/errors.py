class LedgerError(Exception):
    """Base class for ledger errors."""


class SequenceError(LedgerError):
    """An event did not carry the next expected sequence number."""


class AccountNotFound(LedgerError, KeyError):
    """No events have been recorded for the account."""
