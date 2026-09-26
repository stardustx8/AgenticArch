class EventLog:
    '''Append-only audit trail of inventory movements.'''

    def __init__(self):
        self._events = []

    def record(self, kind, order_id, sku, warehouse, qty):
        self._events.append((kind, order_id, sku, warehouse, qty))

    def entries(self, kind=None):
        return [event for event in self._events if kind is None or event[0] == kind]
