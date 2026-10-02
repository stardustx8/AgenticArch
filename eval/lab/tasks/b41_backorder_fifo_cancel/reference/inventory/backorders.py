import itertools
from dataclasses import dataclass


@dataclass
class Backorder:
    seq: int
    order_id: str
    sku: str
    qty: int


class BackorderQueue:
    '''Open backorders per SKU, oldest first.'''

    def __init__(self):
        self._queues = {}
        self._seq = itertools.count(1)

    def push(self, order_id, sku, qty):
        backorder = Backorder(next(self._seq), order_id, sku, qty)
        self._queues.setdefault(sku, []).append(backorder)
        return backorder

    def open_for(self, sku):
        return list(self._queues.get(sku, []))

    def remove(self, backorder):
        self._queues[backorder.sku].remove(backorder)

    def reduce(self, backorder, qty):
        '''Record a (partial) fill; a fully filled backorder leaves the queue.'''
        backorder.qty -= qty
        if backorder.qty <= 0:
            self.remove(backorder)

    def drop_order(self, order_id):
        '''Remove every open backorder of an order and return them.'''
        dropped = []
        for sku, queue in self._queues.items():
            dropped.extend(item for item in queue if item.order_id == order_id)
            self._queues[sku] = [item for item in queue if item.order_id != order_id]
        return dropped

    def outstanding(self, order_id):
        '''{sku: qty} still waiting for an order.'''
        totals = {}
        for queue in self._queues.values():
            for backorder in queue:
                if backorder.order_id == order_id:
                    totals[backorder.sku] = totals.get(backorder.sku, 0) + backorder.qty
        return totals
