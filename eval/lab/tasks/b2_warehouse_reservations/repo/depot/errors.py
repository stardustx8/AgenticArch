"""Exceptions raised by the depot package."""


class DepotError(Exception):
    """Base class for depot errors."""


class OutOfStock(DepotError):
    """Raised when a request asks for more units than can be supplied."""

    def __init__(self, sku: str, requested: int, available: int) -> None:
        super().__init__(f"{sku}: requested {requested}, only {available} available")
        self.sku = sku
        self.requested = requested
        self.available = available
