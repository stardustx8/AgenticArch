from .errors import InsufficientStock, InvalidQuantity


class Allocator:
    def __init__(self, ledger, book, backorders, events):
        self.ledger = ledger
        self.book = book
        self.backorders = backorders
        self.events = events

    def reserve(self, order_id, sku, qty, allow_backorder=False):
        '''Reserve qty units, taking warehouses in priority order.

        Returns the number of units actually reserved. The shortfall is backordered when
        allow_backorder is set; otherwise nothing is reserved and InsufficientStock is raised.'''
        if qty <= 0:
            raise InvalidQuantity(f'quantity must be positive, got {qty}')
        available = self.ledger.free(sku)
        if available < qty and not allow_backorder:
            raise InsufficientStock(sku, qty, available)
        remaining = qty
        for warehouse in self.ledger.warehouses:
            if remaining == 0:
                break
            take = min(remaining, self.ledger.free(sku, warehouse))
            if take:
                self.ledger.take(sku, warehouse, take)
                self.book.add(order_id, sku, warehouse, take)
                self.events.record('reserved', order_id, sku, warehouse, take)
                remaining -= take
        if remaining:
            self.backorders.push(order_id, sku, remaining)
            self.events.record('backordered', order_id, sku, None, remaining)
        return qty - remaining
