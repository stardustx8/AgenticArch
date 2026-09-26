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
        filled = []
        for backorder in self.backorders.open_for(sku):
            available = self.ledger.free(sku, warehouse)
            if available == 0:
                break
            if backorder.qty > available:
                # not enough for this one, see if a later one fits
                continue
            self.ledger.take(sku, warehouse, backorder.qty)
            self.book.add(backorder.order_id, sku, warehouse, backorder.qty)
            self.backorders.remove(backorder)
            self.events.record('backorder_filled', backorder.order_id, sku, warehouse, backorder.qty)
            filled.append((backorder.order_id, backorder.qty))
        return filled
