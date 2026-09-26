from .allocator import Allocator
from .backorders import BackorderQueue
from .errors import UnknownOrder
from .events import EventLog
from .receiving import Receiver
from .reservations import ReservationBook
from .stock import StockLedger


class InventoryService:
    def __init__(self, warehouses=('east', 'west')):
        self.ledger = StockLedger(warehouses)
        self.book = ReservationBook()
        self.backorders = BackorderQueue()
        self.events = EventLog()
        self.allocator = Allocator(self.ledger, self.book, self.backorders, self.events)
        self.receiver = Receiver(self.ledger, self.book, self.backorders, self.events)
        self._orders = set()

    def reserve(self, order_id, sku, qty, allow_backorder=False):
        reserved = self.allocator.reserve(order_id, sku, qty, allow_backorder)
        self._orders.add(order_id)
        return reserved

    def receive(self, sku, warehouse, qty):
        return self.receiver.receive(sku, warehouse, qty)

    def cancel_order(self, order_id):
        '''Cancel an order and give its reserved units back. Returns the released reservations.'''
        if order_id not in self._orders:
            raise UnknownOrder(order_id)
        self._orders.discard(order_id)
        released = self.book.remove_order(order_id)
        for reservation in released:
            self.ledger.add(reservation.sku, reservation.warehouse, reservation.qty)
            self.events.record('released', order_id, reservation.sku, reservation.warehouse, reservation.qty)
        return released

    def free(self, sku, warehouse=None):
        return self.ledger.free(sku, warehouse)

    def reserved(self, order_id):
        return self.book.totals_for(order_id)

    def backordered(self, order_id):
        return self.backorders.outstanding(order_id)
