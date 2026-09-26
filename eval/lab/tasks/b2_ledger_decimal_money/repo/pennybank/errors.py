class PennybankError(Exception):
    """Base class for ledger errors."""


class InsufficientFunds(PennybankError):
    def __init__(self, requested, available) -> None:
        super().__init__(f"cannot withdraw {requested}: only {available} available")
        self.requested = requested
        self.available = available
