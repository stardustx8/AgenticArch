class InventoryError(Exception):
    pass


class InvalidQuantity(InventoryError, ValueError):
    pass


class InsufficientStock(InventoryError):
    def __init__(self, sku, requested, available):
        super().__init__(f'{sku}: requested {requested}, only {available} available')
        self.sku = sku
        self.requested = requested
        self.available = available


class UnknownOrder(InventoryError):
    pass
