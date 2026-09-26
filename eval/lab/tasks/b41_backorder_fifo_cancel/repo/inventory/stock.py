from .errors import InsufficientStock, InvalidQuantity


class StockLedger:
    '''Free (unreserved) units per SKU and warehouse.'''

    def __init__(self, warehouses):
        # allocation priority order
        self.warehouses = list(warehouses)
        self._free = {}

    def free(self, sku, warehouse=None):
        if warehouse is None:
            return sum(self._free.get((sku, name), 0) for name in self.warehouses)
        return self._free.get((sku, warehouse), 0)

    def add(self, sku, warehouse, qty):
        if warehouse not in self.warehouses:
            raise KeyError(f'unknown warehouse {warehouse!r}')
        if qty <= 0:
            raise InvalidQuantity(f'quantity must be positive, got {qty}')
        self._free[(sku, warehouse)] = self.free(sku, warehouse) + qty

    def take(self, sku, warehouse, qty):
        available = self.free(sku, warehouse)
        if qty > available:
            raise InsufficientStock(sku, qty, available)
        self._free[(sku, warehouse)] = available - qty
