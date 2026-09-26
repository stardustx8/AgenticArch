"""Exceptions raised by the stockroom package."""


class InventoryError(Exception):
    """Base class for inventory problems."""


class InsufficientStock(InventoryError):
    """Raised when a removal asks for more units than are on hand."""
