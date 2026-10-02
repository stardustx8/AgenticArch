class LedgerError(Exception):
    """Base class for ledger errors."""


class SequenceError(LedgerError):
    """An event did not carry the next expected sequence number."""
