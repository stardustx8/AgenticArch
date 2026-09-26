"""Exceptions raised by the stockroom package."""


class InventoryError(Exception):
    """Base class for inventory problems."""


class InsufficientStock(InventoryError):
    """Raised when a removal asks for more units than are on hand."""

    def __init__(self, sku: str, requested: int, available: int) -> None:
        super().__init__(
            f"cannot remove {requested} x {sku!r}: only {available} available"
        )
        self.sku = sku
        self.requested = requested
        self.available = available
