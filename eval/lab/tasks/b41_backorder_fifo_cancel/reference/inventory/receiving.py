class Receiver:
    def __init__(self, ledger, book, backorders, events):
        self.ledger = ledger
        self.book = book
        self.backorders = backorders
        self.events = events

    def receive(self, sku, warehouse, qty):
        '''Book incoming stock and hand it to open backorders for the SKU.

        Returns [(order_id, qty), ...] for the backorders that got units.'''
        self.ledger.add(sku, warehouse, qty)
        self.events.record('received', None, sku, warehouse, qty)
        return self.fill_backorders(sku, warehouse)

    def fill_backorders(self, sku, warehouse):
        '''Give free units in the warehouse to open backorders, strictly oldest first.

        The oldest backorder takes as much as it can (possibly only part of what it
        needs); nobody behind it gets anything while it is still open.'''
        filled = []
        for backorder in self.backorders.open_for(sku):
            available = self.ledger.free(sku, warehouse)
            if available == 0:
                break
            take = min(backorder.qty, available)
            self.ledger.take(sku, warehouse, take)
            self.book.add(backorder.order_id, sku, warehouse, take)
            self.backorders.reduce(backorder, take)
            self.events.record('backorder_filled', backorder.order_id, sku, warehouse, take)
            filled.append((backorder.order_id, take))
        return filled
